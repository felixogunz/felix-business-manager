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
    needs_password_rehash,
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

GUEST_TRIAL_HOURS = 48


def normalize_email(email: str) -> str:
    """Normalize an email address for consistent account lookups."""
    return email.strip().lower()


def hash_reset_token(token: str) -> str:
    """Store only a SHA-256 hash of the reset token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def email_is_configured() -> bool:
    """Check that the required SMTP settings are present."""
    return all(
        str(value).strip()
        for value in (
            settings.SMTP_HOST,
            settings.SMTP_USERNAME,
            settings.SMTP_PASSWORD,
            settings.SMTP_FROM_EMAIL,
        )
    )


def send_password_reset_email(email: str, token: str) -> None:
    """Send a password-reset link using the configured SMTP sender."""
    if not email_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password recovery email is not configured.",
        )

    base_url = settings.PASSWORD_RESET_URL.strip()
    separator = "&" if "?" in base_url else "?"
    reset_link = f"{base_url}{separator}reset_token={token}"

    message = EmailMessage()
    message["Subject"] = "Reset your Felix Business Manager password"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        "A password reset was requested for your Felix Business Manager "
        "account.\n\n"
        "Use the link below to choose a new password. It expires in "
        "30 minutes and can only be used once.\n\n"
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
                server.ehlo()

                if settings.SMTP_USE_TLS:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()

                server.login(
                    settings.SMTP_USERNAME,
                    settings.SMTP_PASSWORD,
                )
                server.send_message(message)

    except (OSError, smtplib.SMTPException):
        # Log the technical error on the server; do not expose credentials
        # or SMTP details to the user.
        logger.exception("Password-reset email delivery failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The password-reset email could not be sent. "
                "Please try again later."
            ),
        ) from None

@router.post(
    "/guest",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_guest_session(
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    trial_expires_at = now + timedelta(hours=GUEST_TRIAL_HOURS)

    # Generate a unique internal email for this guest.
    guest_email = (
        f"guest+{secrets.token_hex(16)}@example.com"
    )

    # Guests receive an unpredictable password they never need to enter.
    temporary_password = secrets.token_urlsafe(48)

    guest = User(
        full_name="Guest User",
        email=guest_email,
        hashed_password=hash_password(temporary_password),
        is_active=True,
        is_guest=True,
        trial_started_at=now,
        trial_expires_at=trial_expires_at,
    )

    db.add(guest)

    try:
        db.commit()
        db.refresh(guest)

    except IntegrityError:
        db.rollback()
        logger.exception("Could not create guest account.")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to start your guest trial. Please try again.",
        ) from None

    return {
        "access_token": create_access_token(
            str(guest.id),
            expires_delta=timedelta(days=30),            
            additional_claims={"kind": "guest"},
        ),
        "token_type": "bearer",
        "user": guest,
    }

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)

def register_user(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
):
    email = normalize_email(str(payload.email))
    guest_user = None

    # If a guest token is supplied, retrieve the existing guest account.
    if credentials is not None:
        try:
            token_payload = decode_access_token(
                credentials.credentials
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from None

        if token_payload.get("kind") == "guest":
            subject = token_payload.get("sub")

            if not isinstance(subject, str) or not subject.isdigit():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid guest authentication token.",
                )

            guest_user = db.get(User, int(subject))

            if (
                guest_user is None
                or not guest_user.is_active
                or not guest_user.is_guest
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Guest account not found or inactive.",
                )

    # Prevent registration with an email belonging to another account.
    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if (
        existing_user is not None
        and (
            guest_user is None
            or existing_user.id != guest_user.id
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    if guest_user is not None:
        # Convert the existing guest account into a permanent account.
        user = guest_user
        user.full_name = payload.full_name
        user.email = email
        user.hashed_password = hash_password(payload.password)
        user.is_guest = False
        user.trial_started_at = None
        user.trial_expires_at = None

    else:
        # Create a new account for ordinary registration.
        user = User(
            full_name=payload.full_name,
            email=email,
            hashed_password=hash_password(payload.password),
            is_active=True,
            is_guest=False,
        )
        db.add(user)

    try:
        db.commit()
        db.refresh(user)

    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "user": user,
    }


@router.post("/login", response_model=TokenResponse)
def login_user(
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    email = normalize_email(str(payload.email))

    user = db.scalar(
        select(User).where(User.email == email)
    )

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

    # Upgrade legacy scrypt hashes to Argon2 after successful login.
    if needs_password_rehash(user.hashed_password):
        user.hashed_password = hash_password(payload.password)

        try:
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            logger.exception(
                "Failed to upgrade password hash for user ID %s",
                user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to complete login. Please try again.",
            )

    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "user": user,
    }

@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    # Check global email configuration before account lookup.
    if not email_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password recovery email is not configured.",
        )

    email = normalize_email(str(payload.email))
    user = db.scalar(
        select(User).where(User.email == email)
    )

    generic_response = {
        "message": (
            "If an active account exists for that email, "
            "a password-reset link will be sent."
        )
    }

    # Unknown or inactive accounts receive the same public response.
    if user is None or not user.is_active:
        return generic_response

    token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = hash_reset_token(token)
    user.password_reset_expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not save password-reset token.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not start password recovery. Please try again.",
        ) from None

    try:
        send_password_reset_email(user.email, token)
    except HTTPException:
        # Do not leave a usable token behind when sending fails.
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None

        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception(
                "Could not clear reset token after email delivery failed."
            )

        raise

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

    # Some databases return naive datetimes even when the column is
    # timezone-aware. Treat those stored values as UTC.
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if expiry <= datetime.now(timezone.utc):
        user.password_reset_token_hash = None
        user.password_reset_expires_at = None

        try:
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Could not clear expired reset token.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not complete password recovery.",
            ) from None

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired.",
        )

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not save the new password.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not reset your password. Please try again.",
        ) from None

    return {
        "message": (
            "Your password has been reset successfully. "
            "You can now log in with your new password."
        )
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
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

    except jwt.InvalidTokenError as exc:
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

def require_active_trial(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require guest users to have an active 48-hour trial."""

    if current_user.is_guest:
        expires_at = current_user.trial_expires_at

        if expires_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your guest trial cannot be verified. "
                    "Create a free account to continue."
                ),
            )

        # Handle database timestamps that do not contain timezone data.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) >= expires_at:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your 48-hour guest trial has ended. "
                    "Create a free account to keep using your workspace."
                ),
            )

    return current_user

@router.get("/me", response_model=UserOut)
def read_current_user(
    current_user: User = Depends(get_current_user),
):
    return current_user