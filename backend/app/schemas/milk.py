
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.models.milk import (
    LactationStatus,
    MilkCorrectionTarget,
    MilkingSessionKind,
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


# ============================================================
# Lactation Management
# ============================================================

class LactationCreate(StrictRequest):
    cattle_id: UUID
    sequence_number: int = Field(gt=0, le=100)
    start_date: date


class LactationTransition(StrictRequest):
    status: Literal["DRY", "COMPLETED"]
    effective_date: date


class LactationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    sequence_number: int
    start_date: date
    dry_off_date: date | None
    end_date: date | None
    status: LactationStatus
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


# ============================================================
# Milking Session Management
# ============================================================

class MilkingSessionCreate(StrictRequest):
    cattle_id: UUID
    lactation_id: UUID
    milking_date: date
    session_kind: MilkingSessionKind

    session_code: str = Field(
        min_length=1,
        max_length=50,
    )

    recorded_time: datetime | None = None

    volume_liters: Decimal = Field(
        ge=0,
        max_digits=12,
        decimal_places=3,
    )

    unit: Literal["L"] = "L"
    operator_id: UUID | None = None

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    _clean_text = field_validator(
        "session_code",
        "notes",
    )(_clean)

    _aware_time = field_validator(
        "recorded_time",
    )(_aware)

    @field_validator("session_code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper().replace(" ", "_")

    @model_validator(mode="after")
    def validate_session_code(self):
        if self.session_kind in {
            MilkingSessionKind.MORNING,
            MilkingSessionKind.EVENING,
        }:
            if self.session_code != self.session_kind.value:
                raise ValueError(
                    "Morning/evening session_code must match session_kind"
                )

        elif self.session_code in {"MORNING", "EVENING"}:
            raise ValueError(
                "Additional session_code must be a distinct custom identifier"
            )

        # Preserve the established API policy:
        # milking_date matches the date in the supplied timezone.
        if (
            self.recorded_time is not None
            and self.recorded_time.date() != self.milking_date
        ):
            raise ValueError(
                "recorded_time date must match milking_date"
            )

        return self


class MilkingSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    lactation_id: UUID
    milking_date: date
    session_kind: MilkingSessionKind
    session_code: str
    recorded_time: datetime | None
    volume_liters: Decimal
    unit: str
    operator_id: UUID | None
    notes: str | None
    recorded_by_id: UUID
    recorded_at: datetime
    effective_volume_liters: Decimal | None = None
    effective_notes: str | None = None


class BulkMilkingCreate(StrictRequest):
    records: list[MilkingSessionCreate] = Field(
        min_length=1,
        max_length=100,
    )


class BulkMilkingResponse(BaseModel):
    created: int
    records: list[MilkingSessionResponse]


# ============================================================
# Milk Quality Management
# ============================================================

class QualityCreate(StrictRequest):
    session_id: UUID

    fat_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=6,
        decimal_places=3,
    )

    snf_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=6,
        decimal_places=3,
    )

    protein_percent: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        max_digits=6,
        decimal_places=3,
    )

    density: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=8,
        decimal_places=4,
    )

    temperature_celsius: Decimal | None = Field(
        default=None,
        ge=Decimal("-273.15"),
        max_digits=6,
        decimal_places=2,
    )

    somatic_cell_count: int | None = Field(
        default=None,
        ge=0,
    )

    tested_at: datetime

    notes: str | None = Field(
        default=None,
        max_length=5000,
    )

    _aware_time = field_validator(
        "tested_at",
    )(_aware)

    _clean_notes = field_validator(
        "notes",
    )(_clean)

    @model_validator(mode="after")
    def has_measurement(self):
        values = (
            self.fat_percent,
            self.snf_percent,
            self.protein_percent,
            self.density,
            self.temperature_celsius,
            self.somatic_cell_count,
        )

        if all(value is None for value in values):
            raise ValueError(
                "At least one quality measurement is required"
            )

        return self


class QualityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    session_id: UUID

    fat_percent: Decimal | None
    snf_percent: Decimal | None
    protein_percent: Decimal | None
    density: Decimal | None
    temperature_celsius: Decimal | None
    somatic_cell_count: int | None

    tested_at: datetime
    notes: str | None
    recorded_by_id: UUID
    created_at: datetime

    effective_values: dict[str, Any] | None = None


# ============================================================
# Milk Record Corrections
# ============================================================

class CorrectionCreate(StrictRequest):
    cattle_id: UUID
    target_type: MilkCorrectionTarget
    target_id: UUID

    reason: str = Field(
        min_length=3,
        max_length=500,
    )

    replacement_values: dict[str, Any] = Field(
        min_length=1,
    )

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: Any) -> Any:
        """
        Normalize whitespace before Pydantic validates length.

        Prevents inputs containing only spaces from passing
        the minimum-length validation.
        """
        if not isinstance(value, str):
            return value

        return " ".join(value.split())


class CorrectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    cattle_id: UUID
    target_type: MilkCorrectionTarget
    target_id: UUID
    original_values: dict[str, Any]
    replacement_values: dict[str, Any]
    reason: str
    corrected_by_id: UUID
    created_at: datetime


# ============================================================
# Milk Production Analytics
# ============================================================

class ProductionBucket(BaseModel):
    period_start: date
    volume_liters: Decimal
    recorded_animals: int
    record_count: int


class ProductionSummary(BaseModel):
    date_from: date
    date_to: date
    total_volume_liters: Decimal
    recorded_animals: int
    record_count: int

    average_per_recorded_animal_liters: Decimal | None

    # Missing observations are not interpreted as zero yield.
    missing_records_are_zero: Literal[False] = False

    buckets: list[ProductionBucket]


class SessionTotal(BaseModel):
    session_kind: MilkingSessionKind
    volume_liters: Decimal


class AnimalProductionTotal(BaseModel):
    cattle_id: UUID
    volume_liters: Decimal


class ProductionBreakdown(BaseModel):
    session_totals: list[SessionTotal]
    animal_totals: list[AnimalProductionTotal]

    highest_producing: AnimalProductionTotal | None
    lowest_producing: AnimalProductionTotal | None


# ============================================================
# AI Milk Yield Dataset
# ============================================================

class MilkDatasetRow(BaseModel):
    cattle_id: UUID
    species: str
    breed_id: UUID | None
    date_of_birth: date | None
    lactation_number: int
    milking_date: date
    days_in_milk: int
    session_kind: MilkingSessionKind
    volume_liters: Decimal

    fat_percent: Decimal | None
    snf_percent: Decimal | None
    protein_percent: Decimal | None

    # Currently means a quality sample exists.
    # It does not guarantee every ML feature is populated.
    observation_complete: bool
