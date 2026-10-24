import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.normalization import normalize_email
from app.models.settings_backup import PendingEmailChange
from app.models.user import User


class InvalidEmailChangeToken(ValueError): pass


def issue_email_change(db: Session, *, user: User, new_email: str, lifetime_minutes: int = 30):
    now = datetime.now(timezone.utc); normalized = normalize_email(new_email)
    if db.scalar(select(User.id).where(func.lower(User.email) == normalized, User.id != user.id)): raise ValueError("Email is already registered")
    db.execute(update(PendingEmailChange).where(PendingEmailChange.user_id == user.id, PendingEmailChange.used_at.is_(None), PendingEmailChange.revoked_at.is_(None)).values(revoked_at=now))
    raw = secrets.token_urlsafe(32); record = PendingEmailChange(user_id=user.id, new_email=normalized, token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=now + timedelta(minutes=lifetime_minutes)); db.add(record)
    return raw, record


def verify_email_change(db: Session, raw_token: str) -> User:
    now = datetime.now(timezone.utc); digest = hashlib.sha256(raw_token.encode()).hexdigest()
    record = db.scalar(select(PendingEmailChange).where(PendingEmailChange.token_hash == digest).with_for_update())
    if not record or record.used_at or record.revoked_at or record.expires_at <= now: raise InvalidEmailChangeToken
    user = db.get(User, record.user_id)
    if not user or db.scalar(select(User.id).where(func.lower(User.email) == record.new_email, User.id != user.id)): raise InvalidEmailChangeToken
    user.email = record.new_email; user.email_verified_at = now; user.token_version += 1; record.used_at = now
    db.execute(update(PendingEmailChange).where(PendingEmailChange.user_id == user.id, PendingEmailChange.id != record.id, PendingEmailChange.used_at.is_(None), PendingEmailChange.revoked_at.is_(None)).values(revoked_at=now))
    return user
