import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.normalization import normalize_email
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User


class InvitationAcceptanceError(ValueError):
    pass


def generate_invitation_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash


def expire_stale_pending_invitations(
    db: Session,
    *,
    farm_id,
    email: str,
    now: datetime,
) -> None:
    db.execute(
        update(Invitation)
        .where(
            Invitation.farm_id == farm_id,
            func.lower(func.btrim(Invitation.email))
            == normalize_email(email),
            Invitation.status == InvitationStatus.PENDING,
            Invitation.expires_at <= now,
        )
        .values(status=InvitationStatus.EXPIRED)
    )


def get_redeemable_invitation(
    db: Session,
    *,
    raw_token: str,
    user: User,
    now: datetime | None = None,
) -> Invitation:
    """Validate the invariants a future acceptance endpoint must enforce."""
    checked_at = now or datetime.now(timezone.utc)

    if user.email_verified_at is None:
        raise InvitationAcceptanceError(
            "A verified email address is required"
        )

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    invitation = db.scalar(
        select(Invitation)
        .where(Invitation.token_hash == token_hash)
        .with_for_update()
    )

    if (
        invitation is None
        or invitation.status != InvitationStatus.PENDING
        or invitation.expires_at <= checked_at
    ):
        raise InvitationAcceptanceError(
            "Invitation is invalid, expired, or already used"
        )

    if normalize_email(invitation.email) != normalize_email(user.email):
        raise InvitationAcceptanceError(
            "Invitation does not belong to this verified identity"
        )

    return invitation
