
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    return hash_password("ICMS timing equalization value")


def verify_password_safely(
    plain_password: str,
    hashed_password: str | None,
) -> bool:
    """Perform Argon2 work even when an account does not exist."""
    candidate_hash = hashed_password or _dummy_password_hash()

    try:
        matches = verify_password(plain_password, candidate_hash)
    except Exception:
        matches = False

    return hashed_password is not None and matches


def create_access_token(user_id: UUID) -> str:
    settings = get_settings()

    now = datetime.now(timezone.utc)
    expires = now + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    settings = get_settings()

    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithms=["HS256"],
        options={
            "require": ["sub", "iat", "exp", "type"]
        },
    )
