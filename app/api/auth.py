
import hashlib
import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
bearer_scheme = HTTPBearer(auto_error=False)

RESET_TOKEN_EXPIRE_MINUTES = 30


def hash_reset_token(token: str) -> str:
    """Store only a SHA-256 hash of the reset token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_password_reset_email(email: str, token: str) -> None:
    """Send a time-limited password-reset link through configured SMTP."""
    required_settings = (
        settings.SMTP_HOST,
        settings.SMTP_USERNAME,
        settings.SMTP_PASSWORD,
        settings.SMTP_FROM_EMAIL,
    )

    if not all(required_settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password recovery email is not configured yet.",
        )

    separator = "&" if "?" in settings.PASSWORD_RESET_URL else "?"
    reset_link = (
        f"{settings.PASSWORD_RESET_URL}{separator}"
        f"reset_token={token}"
    )

    message = EmailMessage()
    message["Subject"] = "Reset your Felix Business Manager password"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        "A password reset was requested for your Felix Business Manager "
        "account.\n\n"
        "Use the link below to choose a new password. This link expires "
        "in 30 minutes and can only be used once.\n\n"
        f"{reset_link}\n\n"
        "If you did not request this, you can safely ignore this email."
    )

    try:
        if settings.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                context=ssl.create_default_context(),
                timeout=20,
            ) as server:
                server.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=20,
            ) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls(context=ssl.create_default_context())
                server.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )
                server.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Password-reset email delivery failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The password-reset email could not be sent. Please try again later.",
        )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    existing_user = db.scalar(
        select(User).where(User.email == str(payload.email).lower())
    )

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        email=str(payload.email).lower(),
        hashed_password=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    db.refresh(user)

    access_token = create_access_token(str(user.id))
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    email = str(payload.email).lower()
    user = db.scalar(select(User).where(User.email == email))

    if user is None or not verify_password(
        payload.password,
        user.hashed_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    access_token = create_access_token(str(user.id))
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    # Check global email configuration before checking whether an account
    # exists, so missing SMTP configuration does not reveal account status.
    if not all((
        settings.SMTP_HOST,
        settings.SMTP_USERNAME,
        settings.SMTP_PASSWORD,
        settings.SMTP_FROM_EMAIL,
    )):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password recovery email is not configured yet.",
        )

    email = str(payload.email).lower()
    user = db.scalar(select(User).where(User.email == email))

    generic_response = {
        "message": (
            "If an active account exists for that email, "
            "a password-reset link will be sent."
        )
    }

    if user is None or not user.is_active:
        return generic_response

    token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = hash_reset_token(token)
    user.password_reset_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    )
    db.commit()

    send_password_reset_email(user.email, token)
    return generic_response


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    supplied_hash = hash_reset_token(payload.token)
    user = db.scalar(
        select(User).where(
            User.password_reset_token_hash == supplied_hash
        )
    )

    if user is None or user.password_reset_expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired.",
        )

    expiry = user.password_reset_expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if expiry <= datetime.now(timezone.utc):
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired.",
        )

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    db.commit()

    return {
        "message": (
            "Your password has been reset successfully. "
            "You can now log in with your new password."
        )
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token_payload = decode_access_token(credentials.credentials)
        subject = token_payload.get("sub")

        if not isinstance(subject, str) or not subject.isdigit():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = db.get(User, int(subject))
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.get("/me", response_model=UserOut)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user
