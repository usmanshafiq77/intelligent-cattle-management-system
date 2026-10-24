from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.breeding import (BreedingEventStatus, BreedingMethod, CalvingOutcome, DeliveryType, HeatIntensity, ParentRole, ParentageStatus, PregnancyAssessment, PregnancyLossType, ReminderStatus, ReminderType)
from app.models.cattle import AnimalCategory, AnimalSex, Species


def clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value or None


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HeatObservationCreate(StrictRequest):
    client_request_id: UUID
    cattle_id: UUID
    observed_at: datetime
    signs: str = Field(min_length=2, max_length=4000)
    intensity: HeatIntensity | None = None
    notes: str | None = Field(None, max_length=4000)
    cycle_length_days: int = Field(21, ge=17, le=25)
    create_reminder: bool = True

    _signs = field_validator("signs")(clean)
    _notes = field_validator("notes")(clean)


class HeatObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    cattle_id: UUID
    observed_at: datetime
    signs: str
    intensity: HeatIntensity | None
    notes: str | None
    estimated_next_heat_at: datetime | None
    cycle_length_days: int
    observed_by_id: UUID
    created_at: datetime
    estimate_disclaimer: str = "Estimated from the recorded cycle length; this is not a clinical confirmation."


class BreedingEventCreate(StrictRequest):
    client_request_id: UUID
    cow_id: UUID
    sire_id: UUID | None = None
    method: BreedingMethod
    status: BreedingEventStatus = BreedingEventStatus.PLANNED
    scheduled_at: datetime
    completed_at: datetime | None = None
    semen_reference: str | None = Field(None, max_length=150)
    technician_name: str | None = Field(None, max_length=200)
    follow_up_due_at: datetime | None = None
    notes: str | None = Field(None, max_length=4000)

    @model_validator(mode="after")
    def relationships(self):
        if self.method == BreedingMethod.NATURAL_MATING and not self.sire_id:
            raise ValueError("Natural mating requires a sire")
        if self.status == BreedingEventStatus.COMPLETED and not self.completed_at:
            raise ValueError("Completed breeding requires completed_at")
        if self.completed_at and self.completed_at < self.scheduled_at:
            raise ValueError("completed_at cannot precede scheduled_at")
        if self.follow_up_due_at and self.follow_up_due_at < self.scheduled_at:
            raise ValueError("follow_up_due_at cannot precede scheduled_at")
        return self


class BreedingEventUpdate(StrictRequest):
    status: BreedingEventStatus
    completed_at: datetime | None = None
    follow_up_due_at: datetime | None = None
    notes: str | None = Field(None, max_length=4000)


class BreedingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    cow_id: UUID
    sire_id: UUID | None
    method: BreedingMethod
    status: BreedingEventStatus
    scheduled_at: datetime
    completed_at: datetime | None
    semen_reference: str | None
    technician_name: str | None
    follow_up_due_at: datetime | None
    notes: str | None
    recorded_by_id: UUID
    created_at: datetime
    updated_at: datetime
    conception_disclaimer: str = "A breeding event does not confirm conception or pregnancy."


class PregnancyExaminationCreate(StrictRequest):
    client_request_id: UUID
    cattle_id: UUID
    breeding_event_id: UUID | None = None
    examined_at: datetime
    assessment: PregnancyAssessment
    clinical_assessment: str = Field(min_length=2, max_length=6000)
    expected_calving_date: date | None = None
    gestation_days_used: int | None = Field(None, ge=260, le=310)
    calculate_expected_calving: bool = False
    follow_up_at: datetime | None = None
    notes: str | None = Field(None, max_length=6000)
    supersedes_id: UUID | None = None

    @model_validator(mode="after")
    def clinical_rules(self):
        if self.assessment != PregnancyAssessment.PREGNANT and (self.expected_calving_date or self.calculate_expected_calving):
            raise ValueError("Expected calving is only available for a pregnant assessment")
        if self.expected_calving_date and self.calculate_expected_calving:
            raise ValueError("Provide an expected date or request a calculation, not both")
        if self.follow_up_at and self.follow_up_at < self.examined_at:
            raise ValueError("follow_up_at cannot precede the examination")
        return self


class PregnancyExaminationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    cattle_id: UUID
    breeding_event_id: UUID | None
    examined_at: datetime
    assessment: PregnancyAssessment
    clinical_assessment: str
    expected_calving_date: date | None
    gestation_days_used: int | None
    follow_up_at: datetime | None
    notes: str | None
    examined_by_id: UUID
    supersedes_id: UUID | None
    created_at: datetime
    estimate_disclaimer: str = "Expected calving dates are estimates, not guaranteed delivery dates."


class PregnancyLossCreate(StrictRequest):
    client_request_id: UUID
    cattle_id: UUID
    pregnancy_examination_id: UUID | None = None
    occurred_on: date
    loss_type: PregnancyLossType
    clinical_assessment: str = Field(min_length=2, max_length=6000)
    follow_up_at: datetime | None = None


class PregnancyLossResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    cattle_id: UUID
    pregnancy_examination_id: UUID | None
    occurred_on: date
    loss_type: PregnancyLossType
    clinical_assessment: str
    follow_up_at: datetime | None
    assessed_by_id: UUID
    created_at: datetime


class CalvingEventCreate(StrictRequest):
    client_request_id: UUID
    dam_id: UUID
    breeding_event_id: UUID | None = None
    calved_at: datetime
    outcome: CalvingOutcome
    delivery_type: DeliveryType = DeliveryType.UNKNOWN
    calf_count: int = Field(ge=1, le=8)
    live_count: int = Field(ge=0, le=8)
    stillborn_count: int = Field(ge=0, le=8)
    factual_observations: str | None = Field(None, max_length=6000)
    assistance_details: str | None = Field(None, max_length=4000)
    post_calving_follow_up_at: datetime | None = None

    @model_validator(mode="after")
    def counts(self):
        if self.live_count + self.stillborn_count > self.calf_count:
            raise ValueError("Live and stillborn counts cannot exceed calf_count")
        if self.post_calving_follow_up_at and self.post_calving_follow_up_at < self.calved_at:
            raise ValueError("Follow-up cannot precede calving")
        return self


class CalvingClinicalUpdate(StrictRequest):
    clinical_complications: str = Field(min_length=2, max_length=6000)
    clinical_diagnosis: str | None = Field(None, max_length=6000)
    post_calving_follow_up_at: datetime | None = None


class CalvingEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    dam_id: UUID
    breeding_event_id: UUID | None
    calved_at: datetime
    outcome: CalvingOutcome
    delivery_type: DeliveryType
    calf_count: int
    live_count: int
    stillborn_count: int
    factual_observations: str | None
    assistance_details: str | None
    clinical_complications: str | None
    clinical_diagnosis: str | None
    clinical_recorded_by_id: UUID | None
    post_calving_follow_up_at: datetime | None
    recorded_by_id: UUID
    created_at: datetime


class OffspringCreate(StrictRequest):
    client_request_id: UUID
    tag_number: str = Field(min_length=1, max_length=100)
    name: str | None = Field(None, max_length=150)
    sex: AnimalSex
    species: Species
    category: AnimalCategory = AnimalCategory.CALF
    breed_id: UUID | None = None
    birth_weight_kg: Decimal | None = Field(None, gt=0, le=300)
    sire_id: UUID | None = None
    birth_order: int = Field(ge=1, le=8)
    notes: str | None = Field(None, max_length=4000)


class OffspringResponse(BaseModel):
    id: UUID
    cattle_id: UUID
    calving_event_id: UUID
    tag_number: str
    dam_id: UUID
    sire_id: UUID | None
    birth_order: int


class ParentageCreate(StrictRequest):
    client_request_id: UUID
    child_id: UUID
    parent_id: UUID
    parent_role: ParentRole
    status: ParentageStatus = ParentageStatus.REPORTED
    confidence_percent: Decimal | None = Field(None, ge=0, le=100)
    evidence_reference: str | None = Field(None, max_length=500)


class ParentageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    child_id: UUID
    parent_id: UUID
    parent_role: ParentRole
    status: ParentageStatus
    confidence_percent: Decimal | None
    evidence_reference: str | None
    recorded_by_id: UUID
    created_at: datetime


class PedigreeNode(BaseModel):
    cattle_id: UUID
    tag_number: str
    name: str | None
    sex: AnimalSex
    breed_name: str | None
    generation: int
    relationship: str
    parentage_status: ParentageStatus | None = None
    confidence_percent: Decimal | None = None


class PedigreeResponse(BaseModel):
    subject: PedigreeNode
    ancestors: list[PedigreeNode]
    incomplete: bool
    limitation: str = "This report uses recorded pedigree only; unknown or unverified parentage limits interpretation."


class ReminderCreate(StrictRequest):
    client_request_id: UUID
    cattle_id: UUID
    reminder_type: ReminderType
    due_at: datetime
    title: str = Field(min_length=2, max_length=200)
    notes: str | None = Field(None, max_length=4000)
    assigned_to_id: UUID | None = None
    is_estimate: bool = False


class ReminderUpdate(StrictRequest):
    status: ReminderStatus


class ReminderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    cattle_id: UUID
    reminder_type: ReminderType
    due_at: datetime
    title: str
    notes: str | None
    assigned_to_id: UUID | None
    status: ReminderStatus
    is_estimate: bool
    created_by_id: UUID
    created_at: datetime


class BreedingDashboardResponse(BaseModel):
    heat_observations: int
    planned_breedings: int
    completed_breedings: int
    currently_pregnant: int
    upcoming_calvings: int
    pending_follow_ups: int
    calves_born: int


class BreedingReportResponse(BaseModel):
    date_from: date
    date_to: date
    breeding_events: int
    completed_breedings: int
    confirmed_pregnancies: int
    calving_events: int
    live_calves: int
    stillborn_calves: int
    pregnancy_rate_percent: Decimal | None
    data_note: str
