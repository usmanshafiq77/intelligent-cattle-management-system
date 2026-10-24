import enum
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeedCategory(str, enum.Enum):
    FORAGE = "FORAGE"
    CONCENTRATE = "CONCENTRATE"
    SUPPLEMENT = "SUPPLEMENT"
    MINERAL = "MINERAL"
    OTHER = "OTHER"


class FeedUnit(str, enum.Enum):
    KG = "KG"
    G = "G"
    L = "L"
    ML = "ML"
    BALE = "BALE"


class StockMovementType(str, enum.Enum):
    PURCHASE = "PURCHASE"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    CONSUMPTION = "CONSUMPTION"


class FeedTargetType(str, enum.Enum):
    CATTLE = "CATTLE"
    GROUP = "GROUP"


class ScheduleFrequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    CUSTOM = "CUSTOM"


class NutritionPlanStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    ARCHIVED = "ARCHIVED"


class FeedItem(Base):
    __tablename__ = "feed_items"
    __table_args__ = (
        UniqueConstraint("farm_id", "normalized_name", name="uq_feed_item_farm_name"),
        UniqueConstraint("id", "farm_id", name="uq_feed_item_scope"),
        CheckConstraint("current_quantity >= 0", name="ck_feed_item_stock_nonnegative"),
        CheckConstraint("reorder_level >= 0", name="ck_feed_item_reorder_nonnegative"),
        CheckConstraint(
            "average_unit_cost IS NULL OR average_unit_cost >= 0",
            name="ck_feed_item_average_cost_nonnegative",
        ),
        CheckConstraint(
            "(average_unit_cost IS NULL) = (currency IS NULL)",
            name="ck_feed_item_cost_currency_complete",
        ),
        Index("ix_feed_item_farm_active", "farm_id", "is_active"),
        Index("ix_feed_item_low_stock", "farm_id", "current_quantity", "reorder_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[FeedCategory] = mapped_column(
        Enum(FeedCategory, name="feed_category"), nullable=False
    )
    unit: Mapped[FeedUnit] = mapped_column(Enum(FeedUnit, name="feed_unit"), nullable=False)
    current_quantity: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), server_default="0", nullable=False
    )
    reorder_level: Mapped[Decimal] = mapped_column(
        Numeric(14, 3), default=Decimal("0"), server_default="0", nullable=False
    )
    average_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FeedStockMovement(Base):
    __tablename__ = "feed_stock_movements"
    __table_args__ = (
        UniqueConstraint("farm_id", "client_request_id", name="uq_feed_movement_request"),
        ForeignKeyConstraint(
            ["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"],
            ondelete="RESTRICT", name="fk_feed_movement_item_scope",
        ),
        CheckConstraint("quantity > 0", name="ck_feed_movement_quantity_positive"),
        CheckConstraint("resulting_quantity >= 0", name="ck_feed_movement_result_nonnegative"),
        CheckConstraint(
            "unit_cost IS NULL OR unit_cost >= 0", name="ck_feed_movement_cost_nonnegative"
        ),
        CheckConstraint(
            "(unit_cost IS NULL) = (currency IS NULL)",
            name="ck_feed_movement_cost_currency_complete",
        ),
        CheckConstraint(
            "movement_type = 'PURCHASE' OR unit_cost IS NULL",
            name="ck_feed_movement_cost_purchase_only",
        ),
        Index("ix_feed_movement_history", "farm_id", "feed_item_id", "occurred_at"),
        Index("ix_feed_movement_farm_type", "farm_id", "movement_type", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    feed_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    movement_type: Mapped[StockMovementType] = mapped_column(
        Enum(StockMovementType, name="feed_stock_movement_type"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[FeedUnit] = mapped_column(Enum(FeedUnit, name="feed_unit", create_type=False), nullable=False)
    resulting_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    supplier: Mapped[str | None] = mapped_column(String(200))
    reference: Mapped[str | None] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class FeedingSchedule(Base):
    __tablename__ = "feeding_schedules"
    __table_args__ = (
        UniqueConstraint("id", "farm_id", name="uq_feeding_schedule_scope"),
        UniqueConstraint("farm_id", "normalized_name", name="uq_feeding_schedule_name"),
        ForeignKeyConstraint(
            ["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"],
            ondelete="RESTRICT", name="fk_feeding_schedule_item_scope",
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT", name="fk_feeding_schedule_cattle_scope",
        ),
        CheckConstraint("quantity_per_head > 0", name="ck_feeding_schedule_quantity_positive"),
        CheckConstraint("head_count IS NULL OR head_count > 0", name="ck_feeding_schedule_head_count_positive"),
        CheckConstraint(
            "(target_type = 'CATTLE' AND cattle_id IS NOT NULL AND group_name IS NULL AND head_count IS NULL) OR "
            "(target_type = 'GROUP' AND cattle_id IS NULL AND group_name IS NOT NULL AND head_count IS NOT NULL)",
            name="ck_feeding_schedule_target",
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_feeding_schedule_dates"),
        Index("ix_feeding_schedule_farm_active", "farm_id", "is_active", "start_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)
    feed_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_type: Mapped[FeedTargetType] = mapped_column(Enum(FeedTargetType, name="feed_target_type"), nullable=False)
    cattle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    group_name: Mapped[str | None] = mapped_column(String(150))
    head_count: Mapped[int | None]
    quantity_per_head: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[FeedUnit] = mapped_column(Enum(FeedUnit, name="feed_unit", create_type=False), nullable=False)
    frequency: Mapped[ScheduleFrequency] = mapped_column(Enum(ScheduleFrequency, name="feed_schedule_frequency"), nullable=False)
    days_of_week: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    feeding_time: Mapped[time] = mapped_column(Time, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FeedConsumptionRecord(Base):
    __tablename__ = "feed_consumption_records"
    __table_args__ = (
        UniqueConstraint("id", "farm_id", name="uq_feed_consumption_scope"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_feed_consumption_request"),
        ForeignKeyConstraint(
            ["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"],
            ondelete="RESTRICT", name="fk_feed_consumption_item_scope",
        ),
        ForeignKeyConstraint(
            ["schedule_id", "farm_id"], ["feeding_schedules.id", "feeding_schedules.farm_id"],
            ondelete="RESTRICT", name="fk_feed_consumption_schedule_scope",
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT", name="fk_feed_consumption_cattle_scope",
        ),
        CheckConstraint("quantity > 0", name="ck_feed_consumption_quantity_positive"),
        CheckConstraint("head_count IS NULL OR head_count > 0", name="ck_feed_consumption_head_count_positive"),
        CheckConstraint(
            "(target_type = 'CATTLE' AND cattle_id IS NOT NULL AND group_name IS NULL AND head_count IS NULL) OR "
            "(target_type = 'GROUP' AND cattle_id IS NULL AND group_name IS NOT NULL AND head_count IS NOT NULL)",
            name="ck_feed_consumption_target",
        ),
        Index("ix_feed_consumption_history", "farm_id", "feeding_date", "feed_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    feed_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    target_type: Mapped[FeedTargetType] = mapped_column(Enum(FeedTargetType, name="feed_target_type", create_type=False), nullable=False)
    cattle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    group_name: Mapped[str | None] = mapped_column(String(150))
    head_count: Mapped[int | None]
    feeding_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[FeedUnit] = mapped_column(Enum(FeedUnit, name="feed_unit", create_type=False), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class NutritionPlan(Base):
    __tablename__ = "nutrition_plans"
    __table_args__ = (
        UniqueConstraint("id", "farm_id", name="uq_nutrition_plan_scope"),
        UniqueConstraint("farm_id", "normalized_name", name="uq_nutrition_plan_name"),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT", name="fk_nutrition_plan_cattle_scope",
        ),
        CheckConstraint(
            "(target_type = 'CATTLE' AND cattle_id IS NOT NULL AND group_name IS NULL) OR "
            "(target_type = 'GROUP' AND cattle_id IS NULL AND group_name IS NOT NULL)",
            name="ck_nutrition_plan_target",
        ),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_nutrition_plan_dates"),
        CheckConstraint(
            "(status = 'REVIEWED' AND reviewed_by_id IS NOT NULL AND reviewed_at IS NOT NULL) OR "
            "(status <> 'REVIEWED')",
            name="ck_nutrition_plan_review",
        ),
        Index("ix_nutrition_plan_farm_status", "farm_id", "status", "start_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(150), nullable=False)
    target_type: Mapped[FeedTargetType] = mapped_column(Enum(FeedTargetType, name="feed_target_type", create_type=False), nullable=False)
    cattle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    group_name: Mapped[str | None] = mapped_column(String(150))
    objective: Mapped[str] = mapped_column(String(500), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[NutritionPlanStatus] = mapped_column(
        Enum(NutritionPlanStatus, name="nutrition_plan_status"),
        default=NutritionPlanStatus.DRAFT, server_default=NutritionPlanStatus.DRAFT.value, nullable=False,
    )
    professional_review_required: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class NutritionPlanItem(Base):
    __tablename__ = "nutrition_plan_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["plan_id", "farm_id"], ["nutrition_plans.id", "nutrition_plans.farm_id"],
            ondelete="CASCADE", name="fk_nutrition_plan_item_plan_scope",
        ),
        ForeignKeyConstraint(
            ["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"],
            ondelete="RESTRICT", name="fk_nutrition_plan_item_feed_scope",
        ),
        UniqueConstraint("plan_id", "feed_item_id", name="uq_nutrition_plan_feed"),
        CheckConstraint("daily_quantity_per_head > 0", name="ck_nutrition_plan_item_quantity_positive"),
        Index("ix_nutrition_plan_item_plan", "farm_id", "plan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    feed_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    daily_quantity_per_head: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit: Mapped[FeedUnit] = mapped_column(Enum(FeedUnit, name="feed_unit", create_type=False), nullable=False)
    instructions: Mapped[str | None] = mapped_column(String(500))
