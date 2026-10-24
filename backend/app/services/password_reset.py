
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User, UserStatus


class InvalidPasswordResetTokenError(ValueError):
    """Raised when a reset token is invalid, expired, or already used."""
    pass


def hash_reset_token(raw_token: str) -> str:
    """Hash the reset token before storing or searching for it."""
    return hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


def issue_password_reset_token(
    db: Session,
    *,
    user: User,
    lifetime_minutes: int = 20,
    now: datetime | None = None,
) -> tuple[str, PasswordResetToken]:
    """Issue a single-use password reset token."""

    if lifetime_minutes <= 0:
        raise ValueError("Token lifetime must be positive")

    issued_at = now or datetime.now(timezone.utc)

    # Revoke any previously issued unused reset tokens.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=issued_at)
    )

    raw_token = secrets.token_urlsafe(32)

    token = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_reset_token(raw_token),
        expires_at=issued_at + timedelta(
            minutes=lifetime_minutes
        ),
    )

    db.add(token)

    return raw_token, token


def reset_password_with_token(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
    now: datetime | None = None,
) -> User:
    """
    Validate a reset token, update the user's password,
    and invalidate previously issued JWT sessions.

    The caller must commit the transaction.
    """

    changed_at = now or datetime.now(timezone.utc)

    token = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash
            == hash_reset_token(raw_token)
        )
        .with_for_update()
    )

    if (
        token is None
        or token.used_at is not None
        or token.revoked_at is not None
        or token.expires_at <= changed_at
    ):
        raise InvalidPasswordResetTokenError(
            "Invalid or expired password reset token"
        )

    user = db.scalar(
        select(User)
        .where(User.id == token.user_id)
        .with_for_update()
    )

    if (
        user is None
        or user.status != UserStatus.ACTIVE
        or user.email_verified_at is None
    ):
        raise InvalidPasswordResetTokenError(
            "Invalid or expired password reset token"
        )

    # Update password using existing Argon2 hashing.
    user.password_hash = hash_password(new_password)

    # Invalidate JWTs issued before this reset.
    user.token_version += 1

    # Mark this token as consumed.
    token.used_at = changed_at

    # Revoke other unused reset tokens for this user.
    db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != token.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=changed_at)
    )

    return user
