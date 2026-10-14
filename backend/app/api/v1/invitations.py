
import hashlib
import logging
import secrets

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.session import get_db

from app.models.user import User
from app.models.farm_member import (
    FarmMember,
    FarmRole,
    MemberStatus,
)
from app.models.invitation import (
    Invitation,
    InvitationStatus,
)

from app.schemas.invitation import (
    InvitationCreate,
    InvitationResponse,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/farms",
    tags=["Farm Invitations"],
)


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
):

    # Check that current user owns this farm
    owner_membership = db.scalar(
        select(FarmMember).where(
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == current_user.id,
            FarmMember.role == FarmRole.FARM_OWNER,
            FarmMember.status == MemberStatus.ACTIVE,
        )
    )

    if owner_membership is None:
        raise HTTPException(
            status_code=403,
            detail="Only an active farm owner can invite staff",
        )

    email = str(data.email).strip().lower()

    # Prevent invitations to existing members
    existing_member = db.scalar(
        select(FarmMember)
        .join(User, User.id == FarmMember.user_id)
        .where(
            FarmMember.farm_id == farm_id,
            func.lower(User.email) == email,
        )
    )

    if existing_member is not None:
        raise HTTPException(
            status_code=409,
            detail="This user already has a farm membership",
        )

    now = datetime.now(timezone.utc)

    # Prevent duplicate active invitations
    existing_invitation = db.scalar(
        select(Invitation).where(
            Invitation.farm_id == farm_id,
            func.lower(Invitation.email) == email,
            Invitation.status == InvitationStatus.PENDING,
            Invitation.expires_at > now,
        )
    )

    if existing_invitation is not None:
        raise HTTPException(
            status_code=409,
            detail="An active invitation already exists",
        )

    # Generate a secure random invitation token
    raw_token = secrets.token_urlsafe(32)

    # Only store the token hash in database
    token_hash = hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()

    invitation = Invitation(
        farm_id=farm_id,
        invited_by_id=current_user.id,
        email=email,
        role=FarmRole(data.role),
        token_hash=token_hash,
        status=InvitationStatus.PENDING,
        expires_at=now + timedelta(days=7),
    )

    try:
        db.add(invitation)
        db.commit()
        db.refresh(invitation)

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Invitation creation failed")
        raise HTTPException(
            status_code=500,
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
