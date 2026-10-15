from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.milk.dependencies import MILK_PREFIX, commit_or_error
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.milk import MilkQualityMeasurement
from app.models.user import User
from app.schemas.milk import QualityCreate, QualityResponse
from app.services.milk import effective_quality, scoped_session


router = APIRouter(prefix=f"{MILK_PREFIX}/quality")


@router.post("", response_model=QualityResponse, status_code=status.HTTP_201_CREATED)
def create_quality(
    farm_id: UUID, data: QualityCreate,
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_QUALITY_MANAGE)),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    session = scoped_session(db, farm_id=farm_id, session_id=data.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Milking session not found")
    if data.tested_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="tested_at cannot be in the future")
    if data.tested_at.date() < session.milking_date:
        raise HTTPException(status_code=422, detail="tested_at cannot predate milking_date")
    record = MilkQualityMeasurement(
        farm_id=farm_id, cattle_id=session.cattle_id, session_id=session.id,
        fat_percent=data.fat_percent, snf_percent=data.snf_percent,
        protein_percent=data.protein_percent, density=data.density,
        temperature_celsius=data.temperature_celsius,
        somatic_cell_count=data.somatic_cell_count, tested_at=data.tested_at,
        notes=data.notes, recorded_by_id=current_user.id,
    )
    db.add(record)
    commit_or_error(db, conflict_detail="This quality sample already exists", server_detail="Could not create quality measurement")
    db.refresh(record)
    return effective_quality(db, record)


@router.get("", response_model=list[QualityResponse])
def list_quality(
    farm_id: UUID, cattle_id: UUID | None = None, session_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_VIEW)),
    db: Session = Depends(get_db),
):
    query = select(MilkQualityMeasurement).where(MilkQualityMeasurement.farm_id == farm_id)
    if cattle_id:
        query = query.where(MilkQualityMeasurement.cattle_id == cattle_id)
    if session_id:
        query = query.where(MilkQualityMeasurement.session_id == session_id)
    records = db.scalars(query.order_by(MilkQualityMeasurement.tested_at.desc()).limit(limit).offset(offset))
    return [effective_quality(db, record) for record in records]


@router.get("/{quality_id}", response_model=QualityResponse)
def get_quality(
    farm_id: UUID, quality_id: UUID,
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_VIEW)),
    db: Session = Depends(get_db),
):
    record = db.scalar(select(MilkQualityMeasurement).where(
        MilkQualityMeasurement.id == quality_id, MilkQualityMeasurement.farm_id == farm_id
    ))
    if record is None:
        raise HTTPException(status_code=404, detail="Quality measurement not found")
    return effective_quality(db, record)
