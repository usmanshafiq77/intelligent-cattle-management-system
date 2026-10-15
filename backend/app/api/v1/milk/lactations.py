
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.milk.dependencies import (
    MILK_PREFIX,
    commit_or_error,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import Cattle
from app.models.milk import (
    LactationStatus,
    MilkLactation,
    MilkingSession,
)
from app.models.user import User
from app.schemas.milk import (
    LactationCreate,
    LactationResponse,
    LactationTransition,
)
from app.services.milk import (
    MilkValidationError,
    eligible_cattle,
    scoped_lactation,
    utc_today,
    validate_lactation_dates,
)


router = APIRouter(prefix=f"{MILK_PREFIX}/lactations")


@router.post(
    "",
    response_model=LactationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lactation(
    farm_id: UUID,
    data: LactationCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_LACTATION_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Lock the cattle row before checking overlapping lactations.
        # Concurrent creation requests for the same cattle must wait.
        locked_cattle_id = db.scalar(
            select(Cattle.id)
            .where(
                Cattle.id == data.cattle_id,
                Cattle.farm_id == farm_id,
            )
            .with_for_update()
        )

        if locked_cattle_id is None:
            raise HTTPException(
                status_code=404,
                detail="Cattle not found",
            )

        animal = eligible_cattle(
            db,
            farm_id=farm_id,
            cattle_id=data.cattle_id,
        )

        if data.start_date > utc_today():
            raise MilkValidationError(
                "start_date cannot be in the future"
            )

        if (
            animal.date_of_birth
            and data.start_date < animal.date_of_birth
        ):
            raise MilkValidationError(
                "start_date cannot predate birth"
            )

        validate_lactation_dates(
            db,
            farm_id=farm_id,
            cattle_id=data.cattle_id,
            start_date=data.start_date,
        )

    except MilkValidationError as error:
        raise validation_error(error) from None

    record = MilkLactation(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        sequence_number=data.sequence_number,
        start_date=data.start_date,
        created_by_id=current_user.id,
    )

    db.add(record)

    commit_or_error(
        db,
        conflict_detail="Lactation conflicts with existing data",
        server_detail="Could not create lactation",
    )

    db.refresh(record)
    return record


@router.get(
    "",
    response_model=list[LactationResponse],
)
def list_lactations(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    lactation_status: LactationStatus | None = Query(
        default=None,
        alias="status",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_VIEW)
    ),
    db: Session = Depends(get_db),
):
    query = select(MilkLactation).where(
        MilkLactation.farm_id == farm_id
    )

    if cattle_id is not None:
        query = query.where(
            MilkLactation.cattle_id == cattle_id
        )

    if lactation_status is not None:
        query = query.where(
            MilkLactation.status == lactation_status
        )

    return list(
        db.scalars(
            query.order_by(
                MilkLactation.start_date.desc()
            )
            .limit(limit)
            .offset(offset)
        )
    )


@router.get(
    "/active",
    response_model=LactationResponse,
)
def get_active_lactation(
    farm_id: UUID,
    cattle_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_VIEW)
    ),
    db: Session = Depends(get_db),
):
    record = db.scalar(
        select(MilkLactation).where(
            MilkLactation.farm_id == farm_id,
            MilkLactation.cattle_id == cattle_id,
            MilkLactation.status == LactationStatus.ACTIVE,
        )
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Active lactation not found",
        )

    return record


@router.get(
    "/{lactation_id}",
    response_model=LactationResponse,
)
def get_lactation(
    farm_id: UUID,
    lactation_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_VIEW)
    ),
    db: Session = Depends(get_db),
):
    record = scoped_lactation(
        db,
        farm_id=farm_id,
        lactation_id=lactation_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Lactation not found",
        )

    return record


@router.post(
    "/{lactation_id}/transition",
    response_model=LactationResponse,
)
def transition_lactation(
    farm_id: UUID,
    lactation_id: UUID,
    data: LactationTransition,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_LACTATION_MANAGE)
    ),
    db: Session = Depends(get_db),
):
    # Lock the lactation record during the transition.
    record = scoped_lactation(
        db,
        farm_id=farm_id,
        lactation_id=lactation_id,
        lock=True,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Lactation not found",
        )

    if data.effective_date < record.start_date:
        raise HTTPException(
            status_code=422,
            detail="effective_date cannot predate lactation",
        )

    if data.effective_date > utc_today():
        raise HTTPException(
            status_code=422,
            detail="effective_date cannot be in the future",
        )

    if record.status == LactationStatus.COMPLETED:
        raise HTTPException(
            status_code=422,
            detail="Completed lactation cannot transition",
        )

    # The transition must not invalidate existing milk records.
    latest_milking_date = db.scalar(
        select(func.max(MilkingSession.milking_date)).where(
            MilkingSession.farm_id == farm_id,
            MilkingSession.cattle_id == record.cattle_id,
            MilkingSession.lactation_id == record.id,
        )
    )

    if (
        latest_milking_date is not None
        and data.effective_date < latest_milking_date
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "effective_date cannot predate existing "
                "milking sessions"
            ),
        )

    if data.status == "DRY":
        if record.status != LactationStatus.ACTIVE:
            raise HTTPException(
                status_code=422,
                detail="Only active lactation can be marked dry",
            )

        record.status = LactationStatus.DRY
        record.dry_off_date = data.effective_date

    elif data.status == "COMPLETED":
        # A completed lactation cannot end before its dry-off date.
        if (
            record.status == LactationStatus.DRY
            and record.dry_off_date is not None
            and data.effective_date < record.dry_off_date
        ):
            raise HTTPException(
                status_code=422,
                detail="Completion date cannot predate dry-off date",
            )

        record.status = LactationStatus.COMPLETED
        record.end_date = data.effective_date

    commit_or_error(
        db,
        conflict_detail="Lactation transition conflicts with existing data",
        server_detail="Could not transition lactation",
    )

    db.refresh(record)
    return record
