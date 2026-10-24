import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.email_verification import EmailVerificationToken
from app.models.user import User, UserStatus


class InvalidVerificationTokenError(ValueError):
    pass


def hash_verification_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_verification_token(
    db: Session,
    *,
    user: User,
    lifetime_minutes: int,
    now: datetime | None = None,
) -> tuple[str, EmailVerificationToken]:
    issued_at = now or datetime.now(timezone.utc)

    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=issued_at)
    )

    raw_token = secrets.token_urlsafe(32)
    token = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_verification_token(raw_token),
        expires_at=issued_at + timedelta(minutes=lifetime_minutes),
    )
    db.add(token)
    return raw_token, token


def verify_email_token(
    db: Session,
    *,
    raw_token: str,
    now: datetime | None = None,
) -> User:
    verified_at = now or datetime.now(timezone.utc)
    token_hash = hash_verification_token(raw_token)
    token = db.scalar(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == token_hash)
        .with_for_update()
    )

    if (
        token is None
        or token.used_at is not None
        or token.revoked_at is not None
        or token.expires_at <= verified_at
    ):
        raise InvalidVerificationTokenError

    user = db.get(User, token.user_id)
    if user is None:
        raise InvalidVerificationTokenError

    token.used_at = verified_at
    if user.email_verified_at is None:
        user.email_verified_at = verified_at
    if user.status == UserStatus.PENDING:
        user.status = UserStatus.ACTIVE

    db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.id != token.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=verified_at)
    )

    return user
