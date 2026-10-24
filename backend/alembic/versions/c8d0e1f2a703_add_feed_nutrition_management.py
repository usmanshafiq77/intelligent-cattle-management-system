"""Add farm-scoped feed and nutrition management.

Revision ID: c8d0e1f2a703
Revises: b7c9d2e4f601
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c8d0e1f2a703"
down_revision: Union[str, None] = "b7c9d2e4f601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEED_PERMISSIONS = [
    "feed.record",
    "feed.inventory.manage",
    "feed.schedule.manage",
    "feed.nutrition.view",
    "feed.nutrition.manage",
    "feed.cost.view",
    "feed.reports.view",
]

feed_category = postgresql.ENUM(
    "FORAGE", "CONCENTRATE", "SUPPLEMENT", "MINERAL", "OTHER",
    name="feed_category", create_type=False,
)
feed_unit = postgresql.ENUM(
    "KG", "G", "L", "ML", "BALE", name="feed_unit", create_type=False,
)
movement_type = postgresql.ENUM(
    "PURCHASE", "ADJUSTMENT_IN", "ADJUSTMENT_OUT", "CONSUMPTION",
    name="feed_stock_movement_type", create_type=False,
)
target_type = postgresql.ENUM(
    "CATTLE", "GROUP", name="feed_target_type", create_type=False,
)
schedule_frequency = postgresql.ENUM(
    "DAILY", "WEEKLY", "CUSTOM", name="feed_schedule_frequency", create_type=False,
)
plan_status = postgresql.ENUM(
    "DRAFT", "REVIEWED", "ARCHIVED", name="nutrition_plan_status", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        feed_category, feed_unit, movement_type, target_type,
        schedule_frequency, plan_status,
    ):
        enum_type.create(bind, checkfirst=True)

    op.execute(sa.text(
        "INSERT INTO permissions (code) "
        "SELECT code FROM unnest(CAST(:codes AS text[])) AS code "
        "ON CONFLICT (code) DO NOTHING"
    ).bindparams(codes=FEED_PERMISSIONS))

    op.create_table(
        "feed_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("normalized_name", sa.String(150), nullable=False),
        sa.Column("category", feed_category, nullable=False),
        sa.Column("unit", feed_unit, nullable=False),
        sa.Column("current_quantity", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("reorder_level", sa.Numeric(14, 3), server_default="0", nullable=False),
        sa.Column("average_unit_cost", sa.Numeric(14, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("farm_id", "normalized_name", name="uq_feed_item_farm_name"),
        sa.UniqueConstraint("id", "farm_id", name="uq_feed_item_scope"),
        sa.CheckConstraint("current_quantity >= 0", name="ck_feed_item_stock_nonnegative"),
        sa.CheckConstraint("reorder_level >= 0", name="ck_feed_item_reorder_nonnegative"),
        sa.CheckConstraint("average_unit_cost IS NULL OR average_unit_cost >= 0", name="ck_feed_item_average_cost_nonnegative"),
        sa.CheckConstraint("(average_unit_cost IS NULL) = (currency IS NULL)", name="ck_feed_item_cost_currency_complete"),
    )
    op.create_index("ix_feed_item_farm_active", "feed_items", ["farm_id", "is_active"])
    op.create_index("ix_feed_item_low_stock", "feed_items", ["farm_id", "current_quantity", "reorder_level"])

    op.create_table(
        "feed_stock_movements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movement_type", movement_type, nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", feed_unit, nullable=False),
        sa.Column("resulting_quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_cost", sa.Numeric(14, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("supplier", sa.String(200)),
        sa.Column("reference", sa.String(150)),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("farm_id", "client_request_id", name="uq_feed_movement_request"),
        sa.ForeignKeyConstraint(["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"], ondelete="RESTRICT", name="fk_feed_movement_item_scope"),
        sa.CheckConstraint("quantity > 0", name="ck_feed_movement_quantity_positive"),
        sa.CheckConstraint("resulting_quantity >= 0", name="ck_feed_movement_result_nonnegative"),
        sa.CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_feed_movement_cost_nonnegative"),
        sa.CheckConstraint("(unit_cost IS NULL) = (currency IS NULL)", name="ck_feed_movement_cost_currency_complete"),
        sa.CheckConstraint("movement_type = 'PURCHASE' OR unit_cost IS NULL", name="ck_feed_movement_cost_purchase_only"),
    )
    op.create_index("ix_feed_movement_history", "feed_stock_movements", ["farm_id", "feed_item_id", "occurred_at"])
    op.create_index("ix_feed_movement_farm_type", "feed_stock_movements", ["farm_id", "movement_type", "occurred_at"])

    op.create_table(
        "feeding_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("normalized_name", sa.String(150), nullable=False),
        sa.Column("feed_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", target_type, nullable=False),
        sa.Column("cattle_id", postgresql.UUID(as_uuid=True)),
        sa.Column("group_name", sa.String(150)),
        sa.Column("head_count", sa.Integer()),
        sa.Column("quantity_per_head", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", feed_unit, nullable=False),
        sa.Column("frequency", schedule_frequency, nullable=False),
        sa.Column("days_of_week", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("feeding_time", sa.Time(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "farm_id", name="uq_feeding_schedule_scope"),
        sa.UniqueConstraint("farm_id", "normalized_name", name="uq_feeding_schedule_name"),
        sa.ForeignKeyConstraint(["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"], ondelete="RESTRICT", name="fk_feeding_schedule_item_scope"),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_feeding_schedule_cattle_scope"),
        sa.CheckConstraint("quantity_per_head > 0", name="ck_feeding_schedule_quantity_positive"),
        sa.CheckConstraint("head_count IS NULL OR head_count > 0", name="ck_feeding_schedule_head_count_positive"),
        sa.CheckConstraint("(target_type = 'CATTLE' AND cattle_id IS NOT NULL AND group_name IS NULL AND head_count IS NULL) OR (target_type = 'GROUP' AND cattle_id IS NULL AND group_name IS NOT NULL AND head_count IS NOT NULL)", name="ck_feeding_schedule_target"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_feeding_schedule_dates"),
    )
    op.create_index("ix_feeding_schedule_farm_active", "feeding_schedules", ["farm_id", "is_active", "start_date"])

    op.create_table(
        "feed_consumption_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True)),
        sa.Column("target_type", target_type, nullable=False),
        sa.Column("cattle_id", postgresql.UUID(as_uuid=True)),
        sa.Column("group_name", sa.String(150)),
        sa.Column("head_count", sa.Integer()),
        sa.Column("feeding_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", feed_unit, nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "farm_id", name="uq_feed_consumption_scope"),
        sa.UniqueConstraint("farm_id", "client_request_id", name="uq_feed_consumption_request"),
        sa.ForeignKeyConstraint(["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"], ondelete="RESTRICT", name="fk_feed_consumption_item_scope"),
        sa.ForeignKeyConstraint(["schedule_id", "farm_id"], ["feeding_schedules.id", "feeding_schedules.farm_id"], ondelete="RESTRICT", name="fk_feed_consumption_schedule_scope"),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_feed_consumption_cattle_scope"),
        sa.CheckConstraint("quantity > 0", name="ck_feed_consumption_quantity_positive"),
        sa.CheckConstraint("head_count IS NULL OR head_count > 0", name="ck_feed_consumption_head_count_positive"),
        sa.CheckConstraint("(target_type = 'CATTLE' AND cattle_id IS NOT NULL AND group_name IS NULL AND head_count IS NULL) OR (target_type = 'GROUP' AND cattle_id IS NULL AND group_name IS NOT NULL AND head_count IS NOT NULL)", name="ck_feed_consumption_target"),
    )
    op.create_index("ix_feed_consumption_history", "feed_consumption_records", ["farm_id", "feeding_date", "feed_item_id"])

    op.create_table(
        "nutrition_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("normalized_name", sa.String(150), nullable=False),
        sa.Column("target_type", target_type, nullable=False),
        sa.Column("cattle_id", postgresql.UUID(as_uuid=True)),
        sa.Column("group_name", sa.String(150)),
        sa.Column("objective", sa.String(500), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date()),
        sa.Column("status", plan_status, server_default="DRAFT", nullable=False),
        sa.Column("professional_review_required", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reviewed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("id", "farm_id", name="uq_nutrition_plan_scope"),
        sa.UniqueConstraint("farm_id", "normalized_name", name="uq_nutrition_plan_name"),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_nutrition_plan_cattle_scope"),
        sa.CheckConstraint("(target_type = 'CATTLE' AND cattle_id IS NOT NULL AND group_name IS NULL) OR (target_type = 'GROUP' AND cattle_id IS NULL AND group_name IS NOT NULL)", name="ck_nutrition_plan_target"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_nutrition_plan_dates"),
        sa.CheckConstraint("(status = 'REVIEWED' AND reviewed_by_id IS NOT NULL AND reviewed_at IS NOT NULL) OR (status <> 'REVIEWED')", name="ck_nutrition_plan_review"),
    )
    op.create_index("ix_nutrition_plan_farm_status", "nutrition_plans", ["farm_id", "status", "start_date"])

    op.create_table(
        "nutrition_plan_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feed_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_quantity_per_head", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit", feed_unit, nullable=False),
        sa.Column("instructions", sa.String(500)),
        sa.ForeignKeyConstraint(["plan_id", "farm_id"], ["nutrition_plans.id", "nutrition_plans.farm_id"], ondelete="CASCADE", name="fk_nutrition_plan_item_plan_scope"),
        sa.ForeignKeyConstraint(["feed_item_id", "farm_id"], ["feed_items.id", "feed_items.farm_id"], ondelete="RESTRICT", name="fk_nutrition_plan_item_feed_scope"),
        sa.UniqueConstraint("plan_id", "feed_item_id", name="uq_nutrition_plan_feed"),
        sa.CheckConstraint("daily_quantity_per_head > 0", name="ck_nutrition_plan_item_quantity_positive"),
    )
    op.create_index("ix_nutrition_plan_item_plan", "nutrition_plan_items", ["farm_id", "plan_id"])


def downgrade() -> None:
    op.drop_index("ix_nutrition_plan_item_plan", table_name="nutrition_plan_items")
    op.drop_table("nutrition_plan_items")
    op.drop_index("ix_nutrition_plan_farm_status", table_name="nutrition_plans")
    op.drop_table("nutrition_plans")
    op.drop_index("ix_feed_consumption_history", table_name="feed_consumption_records")
    op.drop_table("feed_consumption_records")
    op.drop_index("ix_feeding_schedule_farm_active", table_name="feeding_schedules")
    op.drop_table("feeding_schedules")
    op.drop_index("ix_feed_movement_farm_type", table_name="feed_stock_movements")
    op.drop_index("ix_feed_movement_history", table_name="feed_stock_movements")
    op.drop_table("feed_stock_movements")
    op.drop_index("ix_feed_item_low_stock", table_name="feed_items")
    op.drop_index("ix_feed_item_farm_active", table_name="feed_items")
    op.drop_table("feed_items")
    op.execute(sa.text(
        "DELETE FROM farm_role_permissions WHERE permission_code = ANY(:codes)"
    ).bindparams(codes=FEED_PERMISSIONS))
    op.execute(sa.text(
        "DELETE FROM permissions WHERE code = ANY(:codes)"
    ).bindparams(codes=FEED_PERMISSIONS))
    bind = op.get_bind()
    for enum_type in (
        plan_status, schedule_frequency, target_type,
        movement_type, feed_unit, feed_category,
    ):
        enum_type.drop(bind, checkfirst=True)
