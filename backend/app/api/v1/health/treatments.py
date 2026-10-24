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
    HealthDiagnosis,
    HealthEncounter,
    MedicationAdministration,
    TreatmentPlan,
    TreatmentStatus,
)
from app.models.user import User
from app.schemas.health import (
    MedicationAdministrationCreate,
    MedicationAdministrationResponse,
    TreatmentCreate,
    TreatmentResponse,
    TreatmentTransition,
)
from app.services.health import (
    HealthValidationError,
    add_audit_event,
    cattle_for_health_action,
    scoped_record,
    serializable_snapshot,
    validate_active_member,
    validate_event_time,
    validate_treatment_transition,
)


router = APIRouter(prefix=HEALTH_PREFIX)


@router.post(
    "/treatments",
    response_model=TreatmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_treatment(
    farm_id: UUID,
    data: TreatmentCreate,
    access: FarmAccess = Depends(
        require_veterinarian_permission(Permission.HEALTH_TREATMENT_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        cattle_for_health_action(
            db, farm_id=farm_id, cattle_id=data.cattle_id
        )
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.prescribed_by_id,
            field_name="prescribed_by_id",
        )
    except HealthValidationError as error:
        raise validation_error(error) from None
    if data.encounter_id and scoped_record(
        db,
        HealthEncounter,
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        record_id=data.encounter_id,
    ) is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    diagnosis = None
    if data.diagnosis_id:
        diagnosis = scoped_record(
            db,
            HealthDiagnosis,
            farm_id=farm_id,
            cattle_id=data.cattle_id,
            record_id=data.diagnosis_id,
        )
        if diagnosis is None:
            raise HTTPException(status_code=404, detail="Diagnosis not found")
        if data.encounter_id and diagnosis.encounter_id != data.encounter_id:
            raise HTTPException(
                status_code=422,
                detail="Diagnosis does not belong to the supplied encounter",
            )
    treatment = TreatmentPlan(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        encounter_id=data.encounter_id,
        diagnosis_id=data.diagnosis_id,
        name=data.name,
        description=data.description,
        medication_name=data.medication_name,
        dosage_quantity=data.dosage_quantity,
        dosage_unit=data.dosage_unit,
        administration_frequency=data.administration_frequency,
        start_date=data.start_date,
        end_date=data.end_date,
        prescribed_by_id=data.prescribed_by_id,
        withdrawal_period_days=data.withdrawal_period_days,
        withdrawal_notes=data.withdrawal_notes,
        follow_up_notes=data.follow_up_notes,
        created_by_id=current_user.id,
    )
    db.add(treatment)
    commit_or_error(
        db,
        conflict_detail="Treatment conflicts with current health data",
        server_detail="Could not create treatment",
    )
    db.refresh(treatment)
    return treatment


@router.get("/treatments", response_model=list[TreatmentResponse])
def list_treatments(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    treatment_status: TreatmentStatus | None = Query(
        default=None, alias="status"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    statement = select(TreatmentPlan).where(TreatmentPlan.farm_id == farm_id)
    if cattle_id:
        statement = statement.where(TreatmentPlan.cattle_id == cattle_id)
    if treatment_status:
        statement = statement.where(TreatmentPlan.status == treatment_status)
    return list(
        db.scalars(
            statement.order_by(
                TreatmentPlan.start_date.desc(), TreatmentPlan.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
    )


@router.post(
    "/treatments/{treatment_id}/transition",
    response_model=TreatmentResponse,
)
def transition_treatment(
    farm_id: UUID,
    treatment_id: UUID,
    data: TreatmentTransition,
    access: FarmAccess = Depends(
        require_veterinarian_permission(Permission.HEALTH_TREATMENT_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    treatment = scoped_record(
        db,
        TreatmentPlan,
        farm_id=farm_id,
        record_id=treatment_id,
        lock=True,
    )
    if treatment is None:
        raise HTTPException(status_code=404, detail="Treatment not found")
    try:
        validate_treatment_transition(treatment.status, data.status)
    except HealthValidationError as error:
        raise validation_error(error) from None
    previous = serializable_snapshot(treatment)
    treatment.status = data.status
    treatment.status_reason = data.reason
    add_audit_event(
        db,
        farm_id=farm_id,
        cattle_id=treatment.cattle_id,
        record_type="TREATMENT",
        record_id=treatment.id,
        action=f"STATUS_{data.status.value}",
        reason=data.reason,
        actor_id=current_user.id,
        previous_data=previous,
    )
    commit_or_error(
        db,
        conflict_detail="Treatment status changed concurrently",
        server_detail="Could not transition treatment",
    )
    db.refresh(treatment)
    return treatment


@router.post(
    "/treatments/{treatment_id}/medication-administrations",
    response_model=MedicationAdministrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def administer_medication(
    farm_id: UUID,
    treatment_id: UUID,
    data: MedicationAdministrationCreate,
    access: FarmAccess = Depends(
        require_veterinarian_permission(Permission.HEALTH_MEDICATION_ADMINISTER)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    treatment = scoped_record(
        db,
        TreatmentPlan,
        farm_id=farm_id,
        record_id=treatment_id,
        lock=True,
    )
    if treatment is None:
        raise HTTPException(status_code=404, detail="Treatment not found")
    if treatment.status not in {
        TreatmentStatus.PLANNED,
        TreatmentStatus.ACTIVE,
    }:
        raise HTTPException(status_code=409, detail="Treatment is not active")
    try:
        animal = cattle_for_health_action(
            db, farm_id=farm_id, cattle_id=treatment.cattle_id
        )
        validate_event_time(
            animal, data.administered_at, field_name="administered_at"
        )
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.administered_by_id,
            field_name="administered_by_id",
        )
        if data.administered_at.date() < treatment.start_date:
            raise HealthValidationError(
                "Medication administration cannot predate treatment"
            )
        if (
            treatment.end_date
            and data.administered_at.date() > treatment.end_date
        ):
            raise HealthValidationError(
                "Medication administration cannot follow treatment end_date"
            )
    except HealthValidationError as error:
        raise validation_error(error) from None
    administration = MedicationAdministration(
        farm_id=farm_id,
        cattle_id=treatment.cattle_id,
        treatment_id=treatment.id,
        medication_name=data.medication_name,
        administered_at=data.administered_at,
        quantity=data.quantity,
        unit=data.unit,
        route=data.route,
        administered_by_id=data.administered_by_id,
        notes=data.notes,
        created_by_id=current_user.id,
    )
    db.add(administration)
    if treatment.status == TreatmentStatus.PLANNED:
        previous = serializable_snapshot(treatment)
        treatment.status = TreatmentStatus.ACTIVE
        treatment.status_reason = "Activated by medication administration"
        add_audit_event(
            db,
            farm_id=farm_id,
            cattle_id=treatment.cattle_id,
            record_type="TREATMENT",
            record_id=treatment.id,
            action="STATUS_ACTIVE",
            reason="Medication administration recorded",
            actor_id=current_user.id,
            previous_data=previous,
        )
    commit_or_error(
        db,
        conflict_detail="This medication administration is already recorded",
        server_detail="Could not record medication administration",
    )
    db.refresh(administration)
    return administration


@router.get(
    "/medication-administrations",
    response_model=list[MedicationAdministrationResponse],
)
def list_medication_administrations(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    treatment_id: UUID | None = None,
    administered_from: datetime | None = None,
    administered_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if (
        administered_from
        and administered_to
        and administered_from > administered_to
    ):
        raise HTTPException(status_code=422, detail="Invalid date range")
    statement = select(MedicationAdministration).where(
        MedicationAdministration.farm_id == farm_id
    )
    if cattle_id:
        statement = statement.where(
            MedicationAdministration.cattle_id == cattle_id
        )
    if treatment_id:
        statement = statement.where(
            MedicationAdministration.treatment_id == treatment_id
        )
    if administered_from:
        statement = statement.where(
            MedicationAdministration.administered_at >= administered_from
        )
    if administered_to:
        statement = statement.where(
            MedicationAdministration.administered_at <= administered_to
        )
    return list(
        db.scalars(
            statement.order_by(
                MedicationAdministration.administered_at.desc(),
                MedicationAdministration.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )
