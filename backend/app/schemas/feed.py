from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.feed import (
    FeedCategory,
    FeedTargetType,
    FeedUnit,
    NutritionPlanStatus,
    ScheduleFrequency,
    StockMovementType,
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeedItemCreate(StrictRequest):
    name: str = Field(min_length=2, max_length=150)
    category: FeedCategory
    unit: FeedUnit
    reorder_level: Decimal = Field(default=0, ge=0, max_digits=14, decimal_places=3)
    description: str | None = Field(default=None, max_length=5000)

    _clean_text = field_validator("name", "description")(_clean)


class FeedItemUpdate(StrictRequest):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    category: FeedCategory | None = None
    reorder_level: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    description: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    _clean_text = field_validator("name", "description")(_clean)

    @model_validator(mode="after")
    def at_least_one_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class FeedItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    name: str
    category: FeedCategory
    unit: FeedUnit
    current_quantity: Decimal
    reorder_level: Decimal
    description: str | None
    is_active: bool
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime
    low_stock: bool = False


class PurchaseCreate(StrictRequest):
    client_request_id: UUID
    feed_item_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: FeedUnit
    unit_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=4)
    currency: str = Field(min_length=3, max_length=3)
    supplier: str | None = Field(default=None, max_length=200)
    reference: str | None = Field(default=None, max_length=150)
    occurred_at: datetime

    _clean_text = field_validator("supplier", "reference")(_clean)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return value.upper()

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value


class StockAdjustmentCreate(StrictRequest):
    client_request_id: UUID
    feed_item_id: UUID
    direction: str = Field(pattern="^(IN|OUT)$")
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: FeedUnit
    reason: str = Field(min_length=3, max_length=500)
    reference: str | None = Field(default=None, max_length=150)
    occurred_at: datetime

    _clean_text = field_validator("reason", "reference")(_clean)
    _aware = field_validator("occurred_at")(PurchaseCreate.require_timezone)


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    feed_item_id: UUID
    client_request_id: UUID
    movement_type: StockMovementType
    quantity: Decimal
    unit: FeedUnit
    resulting_quantity: Decimal
    supplier: str | None
    reference: str | None
    reason: str
    occurred_at: datetime
    recorded_by_id: UUID
    created_at: datetime


class PurchaseResponse(StockMovementResponse):
    unit_cost: Decimal
    currency: str
    total_cost: Decimal


class TargetRequest(StrictRequest):
    target_type: FeedTargetType
    cattle_id: UUID | None = None
    group_name: str | None = Field(default=None, max_length=150)
    head_count: int | None = Field(default=None, gt=0, le=100000)

    _clean_group = field_validator("group_name")(_clean)

    @model_validator(mode="after")
    def validate_target(self):
        if self.target_type == FeedTargetType.CATTLE:
            if self.cattle_id is None or self.group_name is not None or self.head_count is not None:
                raise ValueError("Cattle targets require cattle_id only")
        elif self.cattle_id is not None or self.group_name is None or self.head_count is None:
            raise ValueError("Group targets require group_name and head_count")
        return self


class FeedingScheduleCreate(TargetRequest):
    name: str = Field(min_length=2, max_length=150)
    feed_item_id: UUID
    quantity_per_head: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: FeedUnit
    frequency: ScheduleFrequency
    days_of_week: list[int] = Field(default_factory=list, max_length=7)
    feeding_time: time
    start_date: date
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)

    _clean_text = field_validator("name", "notes")(_clean)

    @model_validator(mode="after")
    def validate_schedule(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        if any(day < 0 or day > 6 for day in self.days_of_week):
            raise ValueError("days_of_week values must be between 0 and 6")
        if len(self.days_of_week) != len(set(self.days_of_week)):
            raise ValueError("days_of_week cannot contain duplicates")
        if self.frequency == ScheduleFrequency.DAILY and self.days_of_week:
            raise ValueError("Daily schedules do not use days_of_week")
        if self.frequency != ScheduleFrequency.DAILY and not self.days_of_week:
            raise ValueError("Weekly/custom schedules require days_of_week")
        return self


class FeedingScheduleUpdate(StrictRequest):
    quantity_per_head: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=3)
    feeding_time: time | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=5000)
    is_active: bool | None = None

    _clean_notes = field_validator("notes")(_clean)

    @model_validator(mode="after")
    def at_least_one_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class FeedingScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    name: str
    feed_item_id: UUID
    target_type: FeedTargetType
    cattle_id: UUID | None
    group_name: str | None
    head_count: int | None
    quantity_per_head: Decimal
    unit: FeedUnit
    frequency: ScheduleFrequency
    days_of_week: list[int]
    feeding_time: time
    start_date: date
    end_date: date | None
    notes: str | None
    is_active: bool
    created_by_id: UUID
    created_at: datetime
    updated_at: datetime


class FeedConsumptionCreate(TargetRequest):
    client_request_id: UUID
    feed_item_id: UUID
    schedule_id: UUID | None = None
    feeding_date: date
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: FeedUnit
    notes: str | None = Field(default=None, max_length=5000)

    _clean_notes = field_validator("notes")(_clean)


class FeedConsumptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    client_request_id: UUID
    feed_item_id: UUID
    schedule_id: UUID | None
    target_type: FeedTargetType
    cattle_id: UUID | None
    group_name: str | None
    head_count: int | None
    feeding_date: date
    quantity: Decimal
    unit: FeedUnit
    notes: str | None
    recorded_by_id: UUID
    recorded_at: datetime


class NutritionPlanLineCreate(StrictRequest):
    feed_item_id: UUID
    daily_quantity_per_head: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit: FeedUnit
    instructions: str | None = Field(default=None, max_length=500)

    _clean_instructions = field_validator("instructions")(_clean)


class NutritionPlanCreate(TargetRequest):
    name: str = Field(min_length=2, max_length=150)
    objective: str = Field(min_length=3, max_length=500)
    notes: str | None = Field(default=None, max_length=5000)
    start_date: date
    end_date: date | None = None
    lines: list[NutritionPlanLineCreate] = Field(min_length=1, max_length=50)

    _clean_text = field_validator("name", "objective", "notes")(_clean)

    @model_validator(mode="after")
    def validate_plan(self):
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        ids = [line.feed_item_id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("Nutrition plan cannot repeat a feed item")
        return self


class NutritionPlanUpdate(StrictRequest):
    status: NutritionPlanStatus


class NutritionPlanLineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    feed_item_id: UUID
    daily_quantity_per_head: Decimal
    unit: FeedUnit
    instructions: str | None


class NutritionPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    farm_id: UUID
    name: str
    target_type: FeedTargetType
    cattle_id: UUID | None
    group_name: str | None
    objective: str
    notes: str | None
    start_date: date
    end_date: date | None
    status: NutritionPlanStatus
    professional_review_required: bool
    created_by_id: UUID
    reviewed_by_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    lines: list[NutritionPlanLineResponse]
    advisory: str = (
        "This farm nutrition plan is operational guidance and is not automatically "
        "veterinarian-approved. Obtain professional review when appropriate."
    )


class LowStockAlert(BaseModel):
    feed_item_id: UUID
    name: str
    unit: FeedUnit
    current_quantity: Decimal
    reorder_level: Decimal
    shortage_quantity: Decimal


class FeedReportSummary(BaseModel):
    date_from: date
    date_to: date
    consumption_quantity_by_unit: dict[str, Decimal]
    consumption_records: int
    purchase_cost_by_currency: dict[str, Decimal] | None = None
    purchase_count: int | None = None


class FeedCostSummary(BaseModel):
    date_from: date
    date_to: date
    purchase_cost_by_currency: dict[str, Decimal]
    purchase_count: int
