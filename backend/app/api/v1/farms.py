
from fastapi import (
    APIRouter,
    Depends,
    status,
)
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.api.dependencies.farms import (
    FarmAccess,
    require_active_farm_member,
)
from app.db.session import get_db
from app.models.user import User
from app.models.farm import Farm
from app.models.farm_member import (
    FarmMember,
    FarmRole,
    MemberStatus,
)
from app.schemas.farm import (
    FarmCreate,
    FarmResponse,
)


router = APIRouter(
    prefix="/farms",
    tags=["Farm Management"],
)


# CREATE FARM
@router.post(
    "",
    response_model=FarmResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_farm(
    data: FarmCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Create farm for authenticated user
    new_farm = Farm(
        name=data.name,
        owner_id=current_user.id,
        location=data.location,
        description=data.description,
    )

    try:
        db.add(new_farm)
        db.flush()

        # Automatically make creator FARM_OWNER
        owner_membership = FarmMember(
            farm_id=new_farm.id,
            user_id=current_user.id,
            role=FarmRole.FARM_OWNER,
            status=MemberStatus.ACTIVE,
        )

        db.add(owner_membership)
        db.flush()

        # Save both records in one transaction
        db.commit()

    except SQLAlchemyError:
        db.rollback()
        raise

    db.refresh(new_farm)

    return new_farm


# GET ALL MY FARMS
@router.get(
    "",
    response_model=list[FarmResponse],
)
def get_my_farms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    statement = (
        select(Farm)
        .join(
            FarmMember,
            FarmMember.farm_id == Farm.id,
        )
        .where(
            FarmMember.user_id == current_user.id,
            FarmMember.status == MemberStatus.ACTIVE,
        )
        .order_by(Farm.created_at.desc())
    )

    return db.scalars(statement).all()


# GET SINGLE FARM
@router.get(
    "/{farm_id}",
    response_model=FarmResponse,
)
def get_farm(
    access: FarmAccess = Depends(require_active_farm_member),
):
    return access.farm
