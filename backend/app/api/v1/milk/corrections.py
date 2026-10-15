import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.milk.dependencies import MILK_PREFIX, commit_or_error, validation_error
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.milk import MilkCorrectionTarget, MilkQualityMeasurement, MilkRecordCorrection
from app.models.user import User
from app.schemas.milk import CorrectionCreate, CorrectionResponse
from app.services.milk import (
    MilkValidationError, QUALITY_CORRECTABLE_FIELDS, SESSION_CORRECTABLE_FIELDS,
    effective_quality, effective_session, scoped_session, validate_correction_values,
)


router = APIRouter(prefix=f"{MILK_PREFIX}/corrections")


@router.post("", response_model=CorrectionResponse, status_code=status.HTTP_201_CREATED)
def create_correction(
    farm_id: UUID, data: CorrectionCreate,
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_CORRECT)),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    if data.target_type == MilkCorrectionTarget.SESSION:
        target = scoped_session(
            db, farm_id=farm_id, session_id=data.target_id,
            cattle_id=data.cattle_id, lock=True,
        )
        if target is None:
            raise HTTPException(status_code=404, detail="Milking session not found")
        current = effective_session(db, target)
        fields = SESSION_CORRECTABLE_FIELDS
    else:
        target = db.scalar(select(MilkQualityMeasurement).where(
            MilkQualityMeasurement.id == data.target_id,
            MilkQualityMeasurement.farm_id == farm_id,
            MilkQualityMeasurement.cattle_id == data.cattle_id,
        ).with_for_update())
        if target is None:
            raise HTTPException(status_code=404, detail="Quality measurement not found")
        current = effective_quality(db, target)
        fields = QUALITY_CORRECTABLE_FIELDS
    try:
        replacements = validate_correction_values(data.target_type, data.replacement_values)
    except MilkValidationError as error:
        raise validation_error(error) from None
    resulting = {field: current.get(field) for field in fields}
    resulting.update(replacements)
    if data.target_type == MilkCorrectionTarget.QUALITY and all(
        resulting.get(field) is None for field in fields - {"notes"}
    ):
        raise HTTPException(status_code=422, detail="At least one quality measurement is required")
    original = json.loads(json.dumps(
        {field: current.get(field) for field in replacements}, default=str
    ))
    complete_replacement = json.loads(json.dumps(resulting, default=str))
    record = MilkRecordCorrection(
        farm_id=farm_id, cattle_id=data.cattle_id, target_type=data.target_type,
        target_id=data.target_id, original_values=original,
        replacement_values=complete_replacement, reason=data.reason,
        corrected_by_id=current_user.id,
    )
    db.add(record)
    commit_or_error(db, conflict_detail="Correction conflicts with current data", server_detail="Could not create milk correction")
    db.refresh(record)
    return record


@router.get("", response_model=list[CorrectionResponse])
def list_corrections(
    farm_id: UUID, target_type: MilkCorrectionTarget | None = None,
    target_id: UUID | None = None, cattle_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_CORRECT)),
    db: Session = Depends(get_db),
):
    query = select(MilkRecordCorrection).where(MilkRecordCorrection.farm_id == farm_id)
    if target_type:
        query = query.where(MilkRecordCorrection.target_type == target_type)
    if target_id:
        query = query.where(MilkRecordCorrection.target_id == target_id)
    if cattle_id:
        query = query.where(MilkRecordCorrection.cattle_id == cattle_id)
    return list(db.scalars(query.order_by(MilkRecordCorrection.created_at.desc(), MilkRecordCorrection.id.desc()).limit(limit).offset(offset)))
