from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.health import (
    DiagnosisSeverity,
    DiagnosisStatus,
    EncounterStatus,
    EncounterType,
    TreatmentStatus,
    VaccinationScheduleStatus,
    VeterinaryVisitStatus,
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("Datetime must include a timezone")
    return value


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EncounterCreate(StrictRequest):
    cattle_id: UUID
    encounter_type: EncounterType
    occurred_at: datetime
    symptoms: str | None = Field(default=None, max_length=5000)
    clinical_observations: str | None = Field(default=None, max_length=10000)
    professional_name: str | None = Field(default=None, max_length=200)
    responsible_user_id: UUID | None = None
    follow_up_due_at: datetime | None = None
    follow_up_notes: str | None = Field(default=None, max_length=5000)
    finalize: bool = False

    _clean_text = field_validator(
        "symptoms",
        "clinical_observations",
        "professional_name",
        "follow_up_notes",
    )(_clean)
    _aware_dates = field_validator("occurred_at", "follow_up_due_at")(_aware)

    @model_validator(mode="after")
    def validate_follow_up(self):
        if self.follow_up_due_at and self.follow_up_due_at < self.occurred_at:
            raise ValueError("follow_up_due_at cannot predate occurred_at")
        return self


class EncounterFinalize(StrictRequest):
    reason: str | None = Field(default=None, max_length=500)

    _clean_reason = field_validator("reason")(_clean)


class EncounterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    encounter_type: EncounterType
    status: EncounterStatus
    occurred_at: datetime
    symptoms: str | None
    clinical_observations: str | None
    professional_name: str | None
    responsible_user_id: UUID | None
    follow_up_due_at: datetime | None
    follow_up_notes: str | None
    created_by_id: UUID
    created_at: datetime
    finalized_at: datetime | None


class DiagnosisCreate(StrictRequest):
    encounter_id: UUID
    condition_name: str = Field(min_length=1, max_length=200)
    standardized_code: str | None = Field(default=None, max_length=50)
    clinical_signs: str | None = Field(default=None, max_length=5000)
    severity: DiagnosisSeverity
    status: DiagnosisStatus = DiagnosisStatus.SUSPECTED
    diagnosed_at: datetime
    responsible_user_id: UUID | None = None
    follow_up_recommendations: str | None = Field(
        default=None, max_length=5000
    )
    clinical_notes: str | None = Field(default=None, max_length=10000)

    _clean_text = field_validator(
        "condition_name",
        "standardized_code",
        "clinical_signs",
        "follow_up_recommendations",
        "clinical_notes",
    )(_clean)
    _aware_date = field_validator("diagnosed_at")(_aware)


class DiagnosisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    encounter_id: UUID
    condition_name: str
    standardized_code: str | None
    clinical_signs: str | None
    severity: DiagnosisSeverity
    status: DiagnosisStatus
    diagnosed_at: datetime
    responsible_user_id: UUID | None
    follow_up_recommendations: str | None
    clinical_notes: str | None
    created_by_id: UUID
    created_at: datetime


class DiagnosisTransition(StrictRequest):
    status: DiagnosisStatus
    reason: str = Field(min_length=3, max_length=500)

    _clean_reason = field_validator("reason")(_clean)


class VaccinationScheduleCreate(StrictRequest):
    cattle_id: UUID
    vaccine_name: str = Field(min_length=1, max_length=200)
    scheduled_date: date
    due_date: date
    responsible_user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=5000)

    _clean_text = field_validator("vaccine_name", "notes")(_clean)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date < self.scheduled_date:
            raise ValueError("due_date cannot predate scheduled_date")
        return self


class VaccinationScheduleUpdate(StrictRequest):
    scheduled_date: date | None = None
    due_date: date | None = None
    responsible_user_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=5000)
    status: Literal["SCHEDULED", "CANCELLED"] | None = None
    reason: str = Field(min_length=3, max_length=500)

    _clean_text = field_validator("notes", "reason")(_clean)


class VaccinationScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    vaccine_name: str
    scheduled_date: date
    due_date: date
    status: VaccinationScheduleStatus
    responsible_user_id: UUID | None
    notes: str | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None


class VaccinationAdministrationCreate(StrictRequest):
    cattle_id: UUID
    schedule_id: UUID | None = None
    vaccine_name: str = Field(min_length=1, max_length=200)
    administered_at: datetime
    dose: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    dose_unit: str = Field(min_length=1, max_length=30)
    route: str | None = Field(default=None, max_length=50)
    batch_lot_number: str | None = Field(default=None, max_length=100)
    expiry_date: date | None = None
    administered_by_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=5000)
    follow_up_due_at: datetime | None = None
    next_due_date: date | None = None

    _clean_text = field_validator(
        "vaccine_name", "dose_unit", "route", "batch_lot_number", "notes"
    )(_clean)
    _aware_dates = field_validator("administered_at", "follow_up_due_at")(_aware)

    @model_validator(mode="after")
    def validate_dates(self):
        day = self.administered_at.date()
        if self.expiry_date and self.expiry_date < day:
            raise ValueError("Vaccine expiry_date cannot predate administration")
        if self.follow_up_due_at and self.follow_up_due_at < self.administered_at:
            raise ValueError("follow_up_due_at cannot predate administration")
        if self.next_due_date and self.next_due_date < day:
            raise ValueError("next_due_date cannot predate administration")
        return self


class VaccinationAdministrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    schedule_id: UUID | None
    vaccine_name: str
    administered_at: datetime
    dose: Decimal
    dose_unit: str
    route: str | None
    batch_lot_number: str | None
    expiry_date: date | None
    administered_by_id: UUID | None
    notes: str | None
    follow_up_due_at: datetime | None
    next_due_date: date | None
    created_by_id: UUID
    created_at: datetime


class TreatmentCreate(StrictRequest):
    cattle_id: UUID
    encounter_id: UUID | None = None
    diagnosis_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    medication_name: str | None = Field(default=None, max_length=200)
    dosage_quantity: Decimal | None = Field(
        default=None, gt=0, max_digits=10, decimal_places=3
    )
    dosage_unit: str | None = Field(default=None, max_length=30)
    administration_frequency: str | None = Field(default=None, max_length=100)
    start_date: date
    end_date: date | None = None
    prescribed_by_id: UUID | None = None
    withdrawal_period_days: int | None = Field(default=None, ge=0, le=3650)
    withdrawal_notes: str | None = Field(default=None, max_length=500)
    follow_up_notes: str | None = Field(default=None, max_length=5000)

    _clean_text = field_validator(
        "name",
        "description",
        "medication_name",
        "dosage_unit",
        "administration_frequency",
        "withdrawal_notes",
        "follow_up_notes",
    )(_clean)

    @model_validator(mode="after")
    def validate_fields(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot predate start_date")
        if (self.dosage_quantity is None) != (self.dosage_unit is None):
            raise ValueError("dosage_quantity and dosage_unit must be paired")
        return self


class TreatmentTransition(StrictRequest):
    status: TreatmentStatus
    reason: str = Field(min_length=3, max_length=500)

    _clean_reason = field_validator("reason")(_clean)


class TreatmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    encounter_id: UUID | None
    diagnosis_id: UUID | None
    name: str
    description: str | None
    medication_name: str | None
    dosage_quantity: Decimal | None
    dosage_unit: str | None
    administration_frequency: str | None
    start_date: date
    end_date: date | None
    status: TreatmentStatus
    prescribed_by_id: UUID | None
    withdrawal_period_days: int | None
    withdrawal_notes: str | None
    follow_up_notes: str | None
    status_reason: str | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class MedicationAdministrationCreate(StrictRequest):
    administered_at: datetime
    medication_name: str = Field(min_length=1, max_length=200)
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    unit: str = Field(min_length=1, max_length=30)
    route: str | None = Field(default=None, max_length=50)
    administered_by_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=5000)

    _clean_text = field_validator(
        "medication_name", "unit", "route", "notes"
    )(_clean)
    _aware_date = field_validator("administered_at")(_aware)


class MedicationAdministrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    treatment_id: UUID
    medication_name: str
    administered_at: datetime
    quantity: Decimal
    unit: str
    route: str | None
    administered_by_id: UUID | None
    notes: str | None
    created_by_id: UUID
    created_at: datetime


class VeterinaryVisitCreate(StrictRequest):
    cattle_id: UUID
    planned_at: datetime | None = None
    veterinarian_user_id: UUID | None = None
    reason: str = Field(min_length=3, max_length=500)

    _clean_reason = field_validator("reason")(_clean)
    _aware_date = field_validator("planned_at")(_aware)


class VeterinaryVisitUpdate(StrictRequest):
    status: VeterinaryVisitStatus
    planned_at: datetime | None = None
    actual_at: datetime | None = None
    veterinarian_user_id: UUID | None = None
    clinical_notes: str | None = Field(default=None, max_length=10000)
    follow_up_due_at: datetime | None = None
    follow_up_notes: str | None = Field(default=None, max_length=5000)
    reason: str = Field(min_length=3, max_length=500)

    _clean_text = field_validator(
        "clinical_notes", "follow_up_notes", "reason"
    )(_clean)
    _aware_dates = field_validator(
        "planned_at", "actual_at", "follow_up_due_at"
    )(_aware)


class VeterinaryVisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    status: VeterinaryVisitStatus
    requested_at: datetime
    planned_at: datetime | None
    actual_at: datetime | None
    veterinarian_user_id: UUID | None
    reason: str
    clinical_notes: str | None
    follow_up_due_at: datetime | None
    follow_up_notes: str | None
    cancellation_reason: str | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class CorrectionCreate(StrictRequest):
    cattle_id: UUID
    record_type: Literal[
        "ENCOUNTER",
        "DIAGNOSIS",
        "VACCINATION_SCHEDULE",
        "VACCINATION_ADMINISTRATION",
        "TREATMENT",
        "MEDICATION_ADMINISTRATION",
        "VETERINARY_VISIT",
    ]
    record_id: UUID
    reason: str = Field(min_length=3, max_length=500)
    correction_note: str = Field(min_length=3, max_length=10000)
    replacement_data: dict[str, Any] | None = None

    _clean_text = field_validator("reason", "correction_note")(_clean)


class CorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    record_type: str
    record_id: UUID
    action: str
    reason: str
    correction_note: str
    previous_data: dict[str, Any] | None
    replacement_data: dict[str, Any] | None
    actor_id: UUID
    created_at: datetime


class HealthReminderResponse(BaseModel):
    kind: Literal[
        "VACCINATION_UPCOMING",
        "VACCINATION_OVERDUE",
        "VETERINARY_VISIT",
        "FOLLOW_UP_OVERDUE",
        "TREATMENT_OUTSTANDING",
    ]
    source_id: UUID
    cattle_id: UUID
    due_at: datetime
    title: str
    overdue: bool


class EncounterRelatedResponse(BaseModel):
    encounter: EncounterResponse
    diagnoses: list[DiagnosisResponse]
    treatments: list[TreatmentResponse]


class AnimalHealthHistoryResponse(BaseModel):
    encounters: list[EncounterResponse]
    diagnoses: list[DiagnosisResponse]
    vaccination_administrations: list[VaccinationAdministrationResponse]
    medication_administrations: list[MedicationAdministrationResponse]
    veterinary_visits: list[VeterinaryVisitResponse]
