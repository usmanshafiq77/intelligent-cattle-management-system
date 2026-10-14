import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess, require_farm_owner
from app.api.v1.auth import get_current_user
from app.core.normalization import normalize_email
from app.db.session import get_db
from app.models.farm_member import FarmMember, FarmRole
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User
from app.schemas.invitation import InvitationCreate, InvitationResponse
from app.services.invitations import (
    expire_stale_pending_invitations,
    generate_invitation_token,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/farms",
    tags=["Farm Invitations"],
)


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


@router.post(
    "/{farm_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    farm_id: UUID,
    data: InvitationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    owner_access: FarmAccess = Depends(require_farm_owner),
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

    return InvitationResponse(
        id=invitation.id,
        farm_id=invitation.farm_id,
        email=invitation.email,
        role=invitation.role,
        status=invitation.status,
        expires_at=invitation.expires_at,
        invitation_token=raw_token,
    )
