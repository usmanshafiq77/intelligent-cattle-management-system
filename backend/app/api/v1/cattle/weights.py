from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.cattle.dependencies import (
    CATTLE_PREFIX,
    animal_or_404,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import CattleWeightRecord
from app.models.user import User
from app.schemas.cattle import WeightCreate, WeightResponse
from app.services.cattle import CattleValidationError, validate_not_future


router = APIRouter(prefix=CATTLE_PREFIX)


@router.post(
    "/{cattle_id}/weights",
    response_model=WeightResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_cattle_weight(
    farm_id: UUID,
    cattle_id: UUID,
    data: WeightCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    animal = animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    try:
        measured_at = validate_not_future(
            data.measured_at, field_name="measured_at"
        )
        if animal.date_of_birth and measured_at.date() < animal.date_of_birth:
            raise CattleValidationError(
                "Weight measurement cannot predate the date of birth"
            )
    except CattleValidationError as error:
        raise validation_error(error) from None
    record = CattleWeightRecord(
        cattle_id=cattle_id,
        farm_id=farm_id,
        weight_kg=data.weight_kg,
        measured_at=measured_at,
        measurement_method=data.measurement_method,
        recorded_by_id=current_user.id,
        notes=data.notes,
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A weight already exists at this exact measurement time",
        ) from None
    return record


@router.get(
    "/{cattle_id}/weights", response_model=list[WeightResponse]
)
def list_cattle_weights(
    farm_id: UUID,
    cattle_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    return db.scalars(
        select(CattleWeightRecord)
        .where(
            CattleWeightRecord.farm_id == farm_id,
            CattleWeightRecord.cattle_id == cattle_id,
        )
        .order_by(
            CattleWeightRecord.measured_at.desc(),
            CattleWeightRecord.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()
