from dataclasses import dataclass
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.farm import Farm
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.user import User


@dataclass(frozen=True)
class FarmAccess:
    farm: Farm
    membership: FarmMember


def require_active_farm_member(
    farm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmAccess:
    farm = db.get(Farm, farm_id)
    membership = db.scalar(
        select(FarmMember).where(
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == current_user.id,
            FarmMember.status == MemberStatus.ACTIVE,
        )
    )

    if farm is None or membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Farm not found",
        )

    return FarmAccess(farm=farm, membership=membership)


def require_farm_owner(
    farm_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FarmAccess:
    farm = db.get(Farm, farm_id)
    membership = db.scalar(
        select(FarmMember).where(
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == current_user.id,
            FarmMember.role == FarmRole.FARM_OWNER,
            FarmMember.status == MemberStatus.ACTIVE,
        )
    )

    if (
        farm is None
        or farm.owner_id != current_user.id
        or membership is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the authoritative active farm owner may do this",
        )

    return FarmAccess(farm=farm, membership=membership)
