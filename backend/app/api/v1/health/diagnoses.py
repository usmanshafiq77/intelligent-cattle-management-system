from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import (
    require_farm_permission,
    require_veterinarian_permission,
)
from app.api.v1.auth import get_current_user
from app.api.v1.health.dependencies import (
    HEALTH_PREFIX,
    commit_or_error,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.health import (
    DiagnosisStatus,
    HealthDiagnosis,
    HealthEncounter,
)
from app.models.user import User
from app.schemas.health import (
    DiagnosisCreate,
    DiagnosisResponse,
    DiagnosisTransition,
)
from app.services.health import (
    HealthValidationError,
    add_audit_event,
    cattle_for_health_action,
    scoped_record,
    serializable_snapshot,
    validate_active_member,
    validate_event_time,
)


router = APIRouter(prefix=HEALTH_PREFIX)

DIAGNOSIS_TRANSITIONS = {
    DiagnosisStatus.SUSPECTED: {
        DiagnosisStatus.CONFIRMED,
        DiagnosisStatus.RULED_OUT,
    },
    DiagnosisStatus.CONFIRMED: {DiagnosisStatus.RESOLVED},
}


@router.post(
    "/diagnoses",
    response_model=DiagnosisResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_diagnosis(
    farm_id: UUID,
    data: DiagnosisCreate,
    access: FarmAccess = Depends(
        require_veterinarian_permission(Permission.HEALTH_DIAGNOSIS)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    encounter = scoped_record(
        db,
        HealthEncounter,
        farm_id=farm_id,
        record_id=data.encounter_id,
    )
    if encounter is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    try:
        animal = cattle_for_health_action(
            db, farm_id=farm_id, cattle_id=encounter.cattle_id
        )
        validate_event_time(
            animal, data.diagnosed_at, field_name="diagnosed_at"
        )
        if data.diagnosed_at < encounter.occurred_at:
            raise HealthValidationError(
                "diagnosed_at cannot predate the related encounter"
            )
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.responsible_user_id,
            field_name="responsible_user_id",
        )
    except HealthValidationError as error:
        raise validation_error(error) from None
    diagnosis = HealthDiagnosis(
        farm_id=farm_id,
        cattle_id=encounter.cattle_id,
        encounter_id=encounter.id,
        condition_name=data.condition_name,
        standardized_code=data.standardized_code,
        clinical_signs=data.clinical_signs,
        severity=data.severity,
        status=data.status,
        diagnosed_at=data.diagnosed_at,
        responsible_user_id=data.responsible_user_id,
        follow_up_recommendations=data.follow_up_recommendations,
        clinical_notes=data.clinical_notes,
        created_by_id=current_user.id,
    )
    db.add(diagnosis)
    commit_or_error(
        db,
        conflict_detail="Diagnosis conflicts with current health data",
        server_detail="Could not record diagnosis",
    )
    db.refresh(diagnosis)
    return diagnosis


@router.get("/diagnoses", response_model=list[DiagnosisResponse])
def list_diagnoses(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    encounter_id: UUID | None = None,
    diagnosis_status: DiagnosisStatus | None = Query(
        default=None, alias="status"
    ),
    diagnosed_from: datetime | None = None,
    diagnosed_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if diagnosed_from and diagnosed_to and diagnosed_from > diagnosed_to:
        raise HTTPException(
            status_code=422,
            detail="diagnosed_from cannot be after diagnosed_to",
        )
    statement = select(HealthDiagnosis).where(
        HealthDiagnosis.farm_id == farm_id
    )
    if cattle_id:
        statement = statement.where(HealthDiagnosis.cattle_id == cattle_id)
    if encounter_id:
        statement = statement.where(
            HealthDiagnosis.encounter_id == encounter_id
        )
    if diagnosis_status:
        statement = statement.where(HealthDiagnosis.status == diagnosis_status)
    if diagnosed_from:
        statement = statement.where(
            HealthDiagnosis.diagnosed_at >= diagnosed_from
        )
    if diagnosed_to:
        statement = statement.where(
            HealthDiagnosis.diagnosed_at <= diagnosed_to
        )
    return list(
        db.scalars(
            statement.order_by(
                HealthDiagnosis.diagnosed_at.desc(), HealthDiagnosis.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/diagnoses/{diagnosis_id}", response_model=DiagnosisResponse)
def get_diagnosis(
    farm_id: UUID,
    diagnosis_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    diagnosis = scoped_record(
        db, HealthDiagnosis, farm_id=farm_id, record_id=diagnosis_id
    )
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    return diagnosis


@router.patch(
    "/diagnoses/{diagnosis_id}/status", response_model=DiagnosisResponse
)
def transition_diagnosis(
    farm_id: UUID,
    diagnosis_id: UUID,
    data: DiagnosisTransition,
    access: FarmAccess = Depends(
        require_veterinarian_permission(Permission.HEALTH_DIAGNOSIS)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    diagnosis = scoped_record(
        db,
        HealthDiagnosis,
        farm_id=farm_id,
        record_id=diagnosis_id,
        lock=True,
    )
    if diagnosis is None:
        raise HTTPException(status_code=404, detail="Diagnosis not found")
    if data.status not in DIAGNOSIS_TRANSITIONS.get(diagnosis.status, set()):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot transition diagnosis from {diagnosis.status.value} "
                f"to {data.status.value}"
            ),
        )
    previous = serializable_snapshot(diagnosis)
    diagnosis.status = data.status
    add_audit_event(
        db,
        farm_id=farm_id,
        cattle_id=diagnosis.cattle_id,
        record_type="DIAGNOSIS",
        record_id=diagnosis.id,
        action=f"STATUS_{data.status.value}",
        reason=data.reason,
        actor_id=current_user.id,
        previous_data=previous,
    )
    commit_or_error(
        db,
        conflict_detail="Diagnosis status changed concurrently",
        server_detail="Could not transition diagnosis",
    )
    db.refresh(diagnosis)
    return diagnosis
