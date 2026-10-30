import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import settings


password_hash = PasswordHash.recommended()

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

SCRYPT_PATTERN = re.compile(
    r"^scrypt:(\d+):(\d+):(\d+)$"
)


def hash_password(password: str) -> str:
    """Create a new Argon2 password hash."""
    return password_hash.hash(password)


def is_legacy_scrypt_hash(hashed_password: str) -> bool:
    """Identify passwords stored using the legacy scrypt format."""
    if not isinstance(hashed_password, str):
        return False

    method = hashed_password.split("$", 1)[0]
    return method.startswith("scrypt:")


def verify_scrypt_password(
    password: str,
    hashed_password: str,
) -> bool:
    """Verify a legacy Werkzeug-compatible scrypt password hash."""

    try:
        parts = hashed_password.split("$")

        if len(parts) != 3:
            return False

        method, salt, stored_digest = parts

        match = SCRYPT_PATTERN.fullmatch(method)

        if not match:
            return False

        n, r, p = map(int, match.groups())

        # Restrict parameters to reasonable values.
        # This prevents malformed hashes from requesting excessive resources.
        if (
            n < 2
            or n > 262144
            or n & (n - 1) != 0
            or r < 1
            or r > 16
            or p < 1
            or p > 4
        ):
            return False

        expected_digest = bytes.fromhex(stored_digest)

        if not expected_digest or len(expected_digest) > 64:
            return False

        calculated_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            n=n,
            r=r,
            p=p,
            dklen=len(expected_digest),
            maxmem=128 * 1024 * 1024,
        )

        return hmac.compare_digest(
            calculated_digest,
            expected_digest,
        )

    except (ValueError, TypeError, OverflowError):
        return False


def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    """Verify either a legacy scrypt hash or a modern Argon2 hash."""

    if not isinstance(hashed_password, str) or not hashed_password:
        return False

    if is_legacy_scrypt_hash(hashed_password):
        return verify_scrypt_password(password, hashed_password)

    try:
        return password_hash.verify(password, hashed_password)
    except Exception:
        return False


def needs_password_rehash(hashed_password: str) -> bool:
    """Return True when a successfully verified legacy hash needs upgrading."""
    return is_legacy_scrypt_hash(hashed_password)


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
    additional_claims: dict | None = None,
) -> str:
    now = datetime.now(timezone.utc)

    expires = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expires,
    }

    if additional_claims:
        payload.update(additional_claims)

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=ALGORITHM,
    )

def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[ALGORITHM],
    )
