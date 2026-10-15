import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cattle import Cattle, CattleStatus
from app.models.farm_member import FarmMember, MemberStatus
from app.models.health import (
    HealthDiagnosis,
    HealthEncounter,
    HealthRecordCorrection,
    MedicationAdministration,
    TreatmentPlan,
    TreatmentStatus,
    VaccinationAdministration,
    VaccinationSchedule,
    VeterinaryVisit,
    VeterinaryVisitStatus,
)


class HealthValidationError(ValueError):
    pass


FINAL_CATTLE_STATUSES = {
    CattleStatus.SOLD,
    CattleStatus.DECEASED,
    CattleStatus.TRANSFERRED,
    CattleStatus.ARCHIVED,
}

TREATMENT_TRANSITIONS = {
    TreatmentStatus.PLANNED: {
        TreatmentStatus.ACTIVE,
        TreatmentStatus.CANCELLED,
    },
    TreatmentStatus.ACTIVE: {
        TreatmentStatus.COMPLETED,
        TreatmentStatus.STOPPED,
    },
}

VISIT_TRANSITIONS = {
    VeterinaryVisitStatus.REQUESTED: {
        VeterinaryVisitStatus.SCHEDULED,
        VeterinaryVisitStatus.CANCELLED,
    },
    VeterinaryVisitStatus.SCHEDULED: {
        VeterinaryVisitStatus.COMPLETED,
        VeterinaryVisitStatus.CANCELLED,
    },
}

RECORD_MODELS = {
    "ENCOUNTER": HealthEncounter,
    "DIAGNOSIS": HealthDiagnosis,
    "VACCINATION_SCHEDULE": VaccinationSchedule,
    "VACCINATION_ADMINISTRATION": VaccinationAdministration,
    "TREATMENT": TreatmentPlan,
    "MEDICATION_ADMINISTRATION": MedicationAdministration,
    "VETERINARY_VISIT": VeterinaryVisit,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def cattle_for_health_action(
    db: Session, *, farm_id: UUID, cattle_id: UUID
) -> Cattle:
    animal = db.scalar(
        select(Cattle).where(
            Cattle.id == cattle_id,
            Cattle.farm_id == farm_id,
        )
    )
    if animal is None:
        raise HealthValidationError("Cattle not found")
    if animal.status in FINAL_CATTLE_STATUSES:
        raise HealthValidationError(
            f"New health actions are not allowed for {animal.status.value} cattle"
        )
    return animal


def validate_event_time(
    animal: Cattle, value: datetime, *, field_name: str
) -> None:
    if value > utc_now():
        raise HealthValidationError(f"{field_name} cannot be in the future")
    if value < animal.created_at:
        raise HealthValidationError(
            f"{field_name} cannot predate cattle registration"
        )
    if animal.date_of_birth and value.date() < animal.date_of_birth:
        raise HealthValidationError(f"{field_name} cannot predate birth")


def validate_active_member(
    db: Session, *, farm_id: UUID, user_id: UUID | None, field_name: str
) -> None:
    if user_id is None:
        return
    exists = db.scalar(
        select(FarmMember.id).where(
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == user_id,
            FarmMember.status == MemberStatus.ACTIVE,
        )
    )
    if exists is None:
        raise HealthValidationError(
            f"{field_name} must identify an active member of this farm"
        )


def scoped_record(
    db: Session,
    model,
    *,
    farm_id: UUID,
    record_id: UUID,
    cattle_id: UUID | None = None,
    lock: bool = False,
):
    statement = select(model).where(
        model.id == record_id,
        model.farm_id == farm_id,
    )
    if cattle_id is not None:
        statement = statement.where(model.cattle_id == cattle_id)
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def validate_treatment_transition(
    current: TreatmentStatus, target: TreatmentStatus
) -> None:
    if target not in TREATMENT_TRANSITIONS.get(current, set()):
        raise HealthValidationError(
            f"Cannot transition treatment from {current.value} to {target.value}"
        )


def validate_visit_transition(
    current: VeterinaryVisitStatus, target: VeterinaryVisitStatus
) -> None:
    if target not in VISIT_TRANSITIONS.get(current, set()):
        raise HealthValidationError(
            f"Cannot transition visit from {current.value} to {target.value}"
        )


def serializable_snapshot(record) -> dict[str, Any]:
    values = {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
    }
    return json.loads(json.dumps(values, default=str))


def add_audit_event(
    db: Session,
    *,
    farm_id: UUID,
    cattle_id: UUID,
    record_type: str,
    record_id: UUID,
    action: str,
    reason: str,
    actor_id: UUID,
    previous_data: dict[str, Any] | None,
    replacement_data: dict[str, Any] | None = None,
    correction_note: str | None = None,
) -> HealthRecordCorrection:
    event = HealthRecordCorrection(
        farm_id=farm_id,
        cattle_id=cattle_id,
        record_type=record_type,
        record_id=record_id,
        action=action,
        reason=reason,
        correction_note=correction_note or reason,
        previous_data=previous_data,
        replacement_data=replacement_data,
        actor_id=actor_id,
    )
    db.add(event)
    return event
