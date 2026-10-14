import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess, require_farm_owner
from app.api.v1.auth import get_current_user
from app.core.config import get_settings
from app.core.normalization import normalize_email
from app.db.session import get_db
from app.models.farm_member import FarmMember, FarmRole
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User
from app.schemas.invitation import (
    InvitationAcceptanceResponse,
    InvitationAcceptRequest,
    InvitationCreate,
    InvitationResponse,
)
from app.services.email_delivery import EmailSender, get_email_sender
from app.services.invitations import (
    InvitationAcceptanceError,
    MembershipAlreadyExistsError,
    accept_invitation,
    expire_stale_farm_invitations,
    expire_stale_pending_invitations,
    generate_invitation_token,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Farm Invitations"],
)


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def _send_invitation_email(
    sender: EmailSender,
    *,
    invitation: Invitation,
    raw_token: str,
    farm_name: str,
) -> None:
    try:
        sender.send_invitation_email(
            recipient=invitation.email,
            token=raw_token,
            expires_at=invitation.expires_at,
            farm_name=farm_name,
        )
    except Exception:
        logger.error(
            "Invitation delivery failed for invitation %s",
            invitation.id,
        )


def _response_token(raw_token: str) -> str | None:
    environment = get_settings().APP_ENV.strip().lower()
    return raw_token if environment in {"development", "local", "test"} else None


def _invitation_response(
    invitation: Invitation, *, raw_token: str | None = None
) -> InvitationResponse:
    return InvitationResponse(
        id=invitation.id,
        farm_id=invitation.farm_id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        accepted_at=invitation.accepted_at,
        invitation_token=(
            _response_token(raw_token) if raw_token is not None else None
        ),
    )


def _farm_invitation_or_404(
    db: Session,
    *,
    farm_id: UUID,
    invitation_id: UUID,
    lock: bool = False,
) -> Invitation:
    statement = select(Invitation).where(
        Invitation.id == invitation_id,
        Invitation.farm_id == farm_id,
    )
    if lock:
        statement = statement.with_for_update()
    invitation = db.scalar(statement)
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found",
        )
    return invitation


@router.post(
    "/farms/{farm_id}/invitations",
    response_model=InvitationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    farm_id: UUID,
    data: InvitationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_access: FarmAccess = Depends(require_farm_owner),
    email_sender: EmailSender = Depends(get_email_sender),
):
    email = normalize_email(str(data.email))
    role = FarmRole(data.role)

    if role == FarmRole.FARM_OWNER:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Farm ownership cannot be granted by invitation",
        )

    existing_member = db.scalar(
        select(FarmMember)
        .join(User, User.id == FarmMember.user_id)
        .where(
            FarmMember.farm_id == owner_access.farm.id,
            func.lower(User.email) == email,
        )
    )
    if existing_member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user already has a farm membership",
        )

    now = datetime.now(timezone.utc)
    expire_stale_pending_invitations(
        db,
        farm_id=owner_access.farm.id,
        email=email,
        now=now,
    )
    db.flush()

    existing_invitation = db.scalar(
        select(Invitation).where(
            Invitation.farm_id == owner_access.farm.id,
            func.lower(func.btrim(Invitation.email)) == email,
            Invitation.status == InvitationStatus.PENDING,
        )
    )
    if existing_invitation is not None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active invitation already exists",
        )

    raw_token, token_hash = generate_invitation_token()
    invitation = Invitation(
        farm_id=owner_access.farm.id,
        invited_by_id=current_user.id,
        email=email,
        role=role,
        token_hash=token_hash,
        status=InvitationStatus.PENDING,
        expires_at=now + timedelta(days=7),
    )

    try:
        db.add(invitation)
        db.commit()
        db.refresh(invitation)
    except IntegrityError as error:
        db.rollback()
        if _constraint_name(error) in {
            "uq_invitations_pending_farm_email",
            "ck_invitations_no_owner_role",
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An active invitation already exists",
            ) from None
        logger.exception("Invitation integrity check failed")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation conflicts with current farm state",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Invitation creation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create invitation",
        ) from None

    _send_invitation_email(
        email_sender,
        invitation=invitation,
        raw_token=raw_token,
        farm_name=owner_access.farm.name,
    )

    return _invitation_response(
        invitation,
        raw_token=raw_token,
    )


@router.get(
    "/farms/{farm_id}/invitations",
    response_model=list[InvitationResponse],
    response_model_exclude_none=True,
)
def list_invitations(
    farm_id: UUID,
    invitation_status: InvitationStatus | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    expire_stale_farm_invitations(
        db, farm_id=farm_id, now=datetime.now(timezone.utc)
    )
    db.commit()
    statement = select(Invitation).where(Invitation.farm_id == farm_id)
    if invitation_status is not None:
        statement = statement.where(Invitation.status == invitation_status)
    invitations = db.scalars(
        statement.order_by(Invitation.created_at.desc(), Invitation.id)
        .limit(limit)
        .offset(offset)
    )
    return [_invitation_response(invitation) for invitation in invitations]


@router.get(
    "/farms/{farm_id}/invitations/{invitation_id}",
    response_model=InvitationResponse,
    response_model_exclude_none=True,
)
def get_invitation(
    farm_id: UUID,
    invitation_id: UUID,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    invitation = _farm_invitation_or_404(
        db, farm_id=farm_id, invitation_id=invitation_id
    )
    if (
        invitation.status == InvitationStatus.PENDING
        and invitation.expires_at <= datetime.now(timezone.utc)
    ):
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
    return _invitation_response(invitation)


@router.post(
    "/farms/{farm_id}/invitations/{invitation_id}/revoke",
    response_model=InvitationResponse,
    response_model_exclude_none=True,
)
def revoke_invitation(
    farm_id: UUID,
    invitation_id: UUID,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    invitation = _farm_invitation_or_404(
        db, farm_id=farm_id, invitation_id=invitation_id, lock=True
    )
    if (
        invitation.status == InvitationStatus.PENDING
        and invitation.expires_at <= datetime.now(timezone.utc)
    ):
        invitation.status = InvitationStatus.EXPIRED
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Expired invitations cannot be revoked",
        )
    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending invitations can be revoked",
        )
    invitation.status = InvitationStatus.REVOKED
    db.commit()
    return _invitation_response(invitation)


@router.post(
    "/farms/{farm_id}/invitations/{invitation_id}/reissue",
    response_model=InvitationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
def reissue_invitation(
    farm_id: UUID,
    invitation_id: UUID,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    email_sender: EmailSender = Depends(get_email_sender),
):
    original = _farm_invitation_or_404(
        db, farm_id=farm_id, invitation_id=invitation_id, lock=True
    )
    if original.status in {
        InvitationStatus.ACCEPTED,
        InvitationStatus.REJECTED,
    }:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Accepted or rejected invitations cannot be reissued",
        )

    now = datetime.now(timezone.utc)
    if original.status == InvitationStatus.PENDING:
        original.status = (
            InvitationStatus.EXPIRED
            if original.expires_at <= now
            else InvitationStatus.REVOKED
        )
        db.flush()

    other_pending = db.scalar(
        select(Invitation.id).where(
            Invitation.farm_id == farm_id,
            Invitation.id != original.id,
            func.lower(func.btrim(Invitation.email))
            == normalize_email(original.email),
            Invitation.status == InvitationStatus.PENDING,
        )
    )
    if other_pending is not None:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An active invitation already exists",
        )

    raw_token, token_hash = generate_invitation_token()
    replacement = Invitation(
        farm_id=farm_id,
        invited_by_id=current_user.id,
        email=normalize_email(original.email),
        role=original.role,
        token_hash=token_hash,
        status=InvitationStatus.PENDING,
        expires_at=now + timedelta(days=7),
    )
    try:
        db.add(replacement)
        db.commit()
        db.refresh(replacement)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation conflicts with current farm state",
        ) from None

    _send_invitation_email(
        email_sender,
        invitation=replacement,
        raw_token=raw_token,
        farm_name=owner_access.farm.name,
    )
    return _invitation_response(replacement, raw_token=raw_token)


@router.post(
    "/invitations/accept",
    response_model=InvitationAcceptanceResponse,
)
def accept_farm_invitation(
    data: InvitationAcceptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        accepted = accept_invitation(
            db,
            raw_token=data.token,
            user=current_user,
        )
        db.commit()
    except MembershipAlreadyExistsError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A membership already exists for this farm",
        ) from None
    except InvitationAcceptanceError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation is invalid or cannot be accepted",
        ) from None
    except IntegrityError as error:
        db.rollback()
        if _constraint_name(error) == "uq_farm_members_farm_user":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A membership already exists for this farm",
            ) from None
        logger.exception("Invitation acceptance integrity check failed")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation conflicts with current farm state",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Invitation acceptance failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not accept invitation",
        ) from None

    accepted_at = accepted.invitation.accepted_at
    if accepted_at is None:
        raise RuntimeError("Accepted invitation is missing its timestamp")

    return InvitationAcceptanceResponse(
        farm_id=accepted.farm.id,
        farm_name=accepted.farm.name,
        membership_id=accepted.membership.id,
        role=accepted.membership.role,
        membership_status=accepted.membership.status,
        accepted_at=accepted_at,
    )
