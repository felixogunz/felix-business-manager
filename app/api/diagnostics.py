import hmac
import os
from importlib.metadata import version, PackageNotFoundError

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.database import get_db
from app.models import User

router = APIRouter(
    prefix="/api/diagnostics",
    tags=["Temporary Diagnostics"],
)


def package_version(package_name: str) -> str:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "Not installed"


@router.get("/password-hash")
def inspect_password_hashes(
    x_diagnostic_key: str | None = Header(
        default=None,
        alias="X-Diagnostic-Key",
    ),
    db: Session = Depends(get_db),
):
    expected_key = os.getenv("DIAGNOSTICS_SECRET", "")

    if (
        not expected_key
        or not x_diagnostic_key
        or not hmac.compare_digest(expected_key, x_diagnostic_key)
    ):
        raise HTTPException(status_code=404, detail="Not found")

    recommended = PasswordHash.recommended()
    argon2_hasher = Argon2Hasher()

    users = db.query(User).limit(10).all()

    results = []

    for user in users:
        stored_hash = user.hashed_password or ""

        results.append({
            "user_id": user.id,
            "hash_prefix": stored_hash[:15],
            "hash_length": len(stored_hash),
            "recommended_recognises": recommended.identify(stored_hash),
            "argon2_recognises": argon2_hasher.identify(stored_hash),
        })

    return {
        "diagnostic": "Password hash inspection",
        "pwdlib_version": package_version("pwdlib"),
        "argon2_version": package_version("argon2-cffi"),
        "users_inspected": len(results),
        "users": results,
    }
