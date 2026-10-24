from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.cattle import (
    AcquisitionMethod,
    AnimalCategory,
    AnimalSex,
    CattleStatus,
    MediaPurpose,
    Species,
)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BreedCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=100)
    species: Species
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Breed name must contain at least 2 characters")
        return cleaned

    _clean_description = field_validator("description")(_clean_optional)


class BreedResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    species: Species
    name: str
    description: str | None
    is_active: bool


class CattleCreate(StrictRequest):
    tag_number: str = Field(min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=150)
    species: Species
    sex: AnimalSex
    category: AnimalCategory
    breed_id: UUID | None = None
    date_of_birth: date | None = None
    birth_date_estimated: bool = False
    acquisition_date: date | None = None
    acquisition_method: AcquisitionMethod = AcquisitionMethod.UNKNOWN
    acquisition_source: str | None = Field(default=None, max_length=255)
    initial_acquisition_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    initial_acquisition_currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"
    )
    color: str | None = Field(default=None, max_length=100)
    identification_marks: str | None = Field(default=None, max_length=500)
    mother_id: UUID | None = None
    father_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=5000)
    initial_weight_kg: Decimal | None = Field(
        default=None, gt=0, le=3000, max_digits=7, decimal_places=2
    )
    initial_weight_measured_at: datetime | None = None
    initial_weight_method: str | None = Field(default=None, max_length=50)

    @field_validator(
        "tag_number",
        "name",
        "acquisition_source",
        "color",
        "identification_marks",
        "notes",
        "initial_weight_method",
    )
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @model_validator(mode="after")
    def validate_related_fields(self):
        if self.initial_weight_kg is None and (
            self.initial_weight_measured_at is not None
            or self.initial_weight_method is not None
        ):
            raise ValueError("Initial weight metadata requires initial_weight_kg")
        if (self.initial_acquisition_cost is None) != (
            self.initial_acquisition_currency is None
        ):
            raise ValueError(
                "Acquisition cost and its ISO currency must be provided together"
            )
        if self.initial_acquisition_currency:
            self.initial_acquisition_currency = (
                self.initial_acquisition_currency.upper()
            )
        return self


class CattleUpdate(StrictRequest):
    tag_number: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, max_length=150)
    category: AnimalCategory | None = None
    breed_id: UUID | None = None
    date_of_birth: date | None = None
    birth_date_estimated: bool | None = None
    acquisition_date: date | None = None
    acquisition_method: AcquisitionMethod | None = None
    acquisition_source: str | None = Field(default=None, max_length=255)
    initial_acquisition_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    initial_acquisition_currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$"
    )
    color: str | None = Field(default=None, max_length=100)
    identification_marks: str | None = Field(default=None, max_length=500)
    mother_id: UUID | None = None
    father_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=5000)

    @field_validator(
        "tag_number",
        "name",
        "acquisition_source",
        "color",
        "identification_marks",
        "notes",
    )
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean_optional(value)

    @field_validator("initial_acquisition_currency")
    @classmethod
    def uppercase_currency(cls, value: str | None) -> str | None:
        return value.upper() if value else None


class WeightCreate(StrictRequest):
    weight_kg: Decimal = Field(
        gt=0, le=3000, max_digits=7, decimal_places=2
    )
    measured_at: datetime
    measurement_method: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=500)

    _clean_method = field_validator("measurement_method")(_clean_optional)
    _clean_notes = field_validator("notes")(_clean_optional)


class WeightResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cattle_id: UUID
    farm_id: UUID
    weight_kg: Decimal
    measured_at: datetime
    measurement_method: str | None
    recorded_by_id: UUID
    notes: str | None
    created_at: datetime


class LifecycleTransitionCreate(StrictRequest):
    new_status: CattleStatus
    effective_at: datetime
    reason: str | None = Field(default=None, max_length=500)

    _clean_reason = field_validator("reason")(_clean_optional)


class LifecycleEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cattle_id: UUID
    farm_id: UUID
    previous_status: CattleStatus | None
    new_status: CattleStatus
    effective_at: datetime
    reason: str | None
    actor_id: UUID
    created_at: datetime


class MediaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    cattle_id: UUID
    farm_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    purpose: MediaPurpose
    uploaded_by_id: UUID
    uploaded_at: datetime


class CattleResponse(BaseModel):
    id: UUID
    farm_id: UUID
    tag_number: str
    name: str | None
    species: Species
    sex: AnimalSex
    category: AnimalCategory
    breed: BreedResponse | None
    date_of_birth: date | None
    birth_date_estimated: bool
    registration_date: date
    acquisition_date: date | None
    acquisition_method: AcquisitionMethod
    acquisition_source: str | None
    initial_acquisition_cost: Decimal | None
    initial_acquisition_currency: str | None
    color: str | None
    identification_marks: str | None
    status: CattleStatus
    mother_id: UUID | None
    father_id: UUID | None
    notes: str | None
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    latest_weight: WeightResponse | None = None
    media_count: int = 0


class CattleSummaryResponse(BaseModel):
    total: int
    female_count: int
    male_count: int
    breed_count: int
    status_counts: dict[CattleStatus, int]
