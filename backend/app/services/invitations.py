import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.normalization import normalize_email
from app.models.farm import Farm
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User


class InvitationAcceptanceError(ValueError):
    pass


class MembershipAlreadyExistsError(InvitationAcceptanceError):
    pass


@dataclass(frozen=True)
class AcceptedInvitation:
    farm: Farm
    membership: FarmMember
    invitation: Invitation


def hash_invitation_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_invitation_token() -> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_invitation_token(raw_token)
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
    """Lock and validate an invitation for the acceptance transaction."""
    checked_at = now or datetime.now(timezone.utc)

    if user.email_verified_at is None:
        raise InvitationAcceptanceError(
            "A verified email address is required"
        )

    token_hash = hash_invitation_token(raw_token)
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


def accept_invitation(
    db: Session,
    *,
    raw_token: str,
    user: User,
    now: datetime | None = None,
) -> AcceptedInvitation:
    accepted_at = now or datetime.now(timezone.utc)
    invitation = get_redeemable_invitation(
        db,
        raw_token=raw_token,
        user=user,
        now=accepted_at,
    )

    if invitation.role == FarmRole.FARM_OWNER:
        raise InvitationAcceptanceError(
            "Farm ownership cannot be granted by invitation"
        )

    farm = db.scalar(
        select(Farm)
        .where(Farm.id == invitation.farm_id)
        .with_for_update()
    )
    if farm is None:
        raise InvitationAcceptanceError("Invitation farm does not exist")

    owner_membership = db.scalar(
        select(FarmMember)
        .where(
            FarmMember.farm_id == farm.id,
            FarmMember.user_id == farm.owner_id,
            FarmMember.role == FarmRole.FARM_OWNER,
            FarmMember.status == MemberStatus.ACTIVE,
        )
        .with_for_update()
    )
    if (
        invitation.invited_by_id != farm.owner_id
        or owner_membership is None
    ):
        raise InvitationAcceptanceError(
            "Invitation is not authorized by the current farm owner"
        )

    existing_membership = db.scalar(
        select(FarmMember)
        .where(
            FarmMember.farm_id == farm.id,
            FarmMember.user_id == user.id,
        )
        .with_for_update()
    )
    if existing_membership is not None:
        raise MembershipAlreadyExistsError(
            "A farm membership already exists for this user"
        )

    membership = FarmMember(
        farm_id=farm.id,
        user_id=user.id,
        role=invitation.role,
        status=MemberStatus.ACTIVE,
    )
    db.add(membership)
    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = accepted_at
    db.flush()

    return AcceptedInvitation(
        farm=farm,
        membership=membership,
        invitation=invitation,
    )
