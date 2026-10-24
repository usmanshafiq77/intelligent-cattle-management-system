from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cattle import Cattle, CattleStatus
from app.models.feed import (
    FeedConsumptionRecord,
    FeedItem,
    FeedStockMovement,
    FeedTargetType,
    FeedUnit,
    FeedingSchedule,
    StockMovementType,
)


class FeedValidationError(ValueError):
    pass


def normalize_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


def scoped_feed_item(
    db: Session, *, farm_id: UUID, feed_item_id: UUID, lock: bool = False
) -> FeedItem | None:
    query = select(FeedItem).where(
        FeedItem.id == feed_item_id,
        FeedItem.farm_id == farm_id,
    )
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def scoped_schedule(
    db: Session, *, farm_id: UUID, schedule_id: UUID
) -> FeedingSchedule | None:
    return db.scalar(
        select(FeedingSchedule).where(
            FeedingSchedule.id == schedule_id,
            FeedingSchedule.farm_id == farm_id,
        )
    )


def validate_cattle_target(
    db: Session,
    *,
    farm_id: UUID,
    target_type: FeedTargetType,
    cattle_id: UUID | None,
) -> None:
    if target_type != FeedTargetType.CATTLE:
        return
    cattle = db.scalar(
        select(Cattle).where(
            Cattle.id == cattle_id,
            Cattle.farm_id == farm_id,
            Cattle.status == CattleStatus.ACTIVE,
        )
    )
    if cattle is None:
        raise FeedValidationError("Active cattle target not found")


def validate_item_unit(item: FeedItem, unit: FeedUnit) -> None:
    if item.unit != unit:
        raise FeedValidationError(
            f"Quantity unit must match the feed inventory unit ({item.unit.value})"
        )
    if not item.is_active:
        raise FeedValidationError("Feed item is inactive")


def apply_stock_movement(
    db: Session,
    *,
    farm_id: UUID,
    feed_item_id: UUID,
    client_request_id: UUID,
    movement_type: StockMovementType,
    quantity: Decimal,
    unit: FeedUnit,
    actor_id: UUID,
    reason: str,
    occurred_at: datetime,
    unit_cost: Decimal | None = None,
    currency: str | None = None,
    supplier: str | None = None,
    reference: str | None = None,
) -> FeedStockMovement:
    item = scoped_feed_item(
        db, farm_id=farm_id, feed_item_id=feed_item_id, lock=True
    )
    if item is None:
        raise FeedValidationError("Feed item not found")
    validate_item_unit(item, unit)

    duplicate = db.scalar(
        select(FeedStockMovement.id).where(
            FeedStockMovement.farm_id == farm_id,
            FeedStockMovement.client_request_id == client_request_id,
        )
    )
    if duplicate is not None:
        raise FeedValidationError("Duplicate stock transaction")

    incoming = movement_type in {
        StockMovementType.PURCHASE,
        StockMovementType.ADJUSTMENT_IN,
    }
    resulting = item.current_quantity + quantity if incoming else item.current_quantity - quantity
    if resulting < 0:
        raise FeedValidationError("Insufficient feed stock")

    if movement_type == StockMovementType.PURCHASE:
        if unit_cost is None or currency is None:
            raise FeedValidationError("Purchases require unit cost and currency")
        if item.currency is not None and item.currency != currency:
            raise FeedValidationError("Purchase currency must match existing inventory currency")
        previous_value = item.current_quantity * (item.average_unit_cost or Decimal("0"))
        purchased_value = quantity * unit_cost
        item.average_unit_cost = (previous_value + purchased_value) / resulting
        item.currency = currency
    elif unit_cost is not None or currency is not None:
        raise FeedValidationError("Only purchases may include cost information")

    item.current_quantity = resulting
    movement = FeedStockMovement(
        farm_id=farm_id,
        feed_item_id=feed_item_id,
        client_request_id=client_request_id,
        movement_type=movement_type,
        quantity=quantity,
        unit=unit,
        resulting_quantity=resulting,
        unit_cost=unit_cost,
        currency=currency,
        supplier=supplier,
        reference=reference,
        reason=reason,
        occurred_at=occurred_at,
        recorded_by_id=actor_id,
    )
    db.add(movement)
    return movement


def record_consumption(
    db: Session,
    *,
    farm_id: UUID,
    client_request_id: UUID,
    feed_item_id: UUID,
    schedule_id: UUID | None,
    target_type: FeedTargetType,
    cattle_id: UUID | None,
    group_name: str | None,
    head_count: int | None,
    feeding_date,
    quantity: Decimal,
    unit: FeedUnit,
    notes: str | None,
    actor_id: UUID,
) -> FeedConsumptionRecord:
    validate_cattle_target(
        db, farm_id=farm_id, target_type=target_type, cattle_id=cattle_id
    )
    if schedule_id is not None:
        schedule = scoped_schedule(db, farm_id=farm_id, schedule_id=schedule_id)
        if schedule is None or not schedule.is_active:
            raise FeedValidationError("Active feeding schedule not found")
        if (
            schedule.feed_item_id != feed_item_id
            or schedule.unit != unit
            or schedule.target_type != target_type
            or schedule.cattle_id != cattle_id
            or schedule.group_name != group_name
        ):
            raise FeedValidationError("Consumption does not match the selected schedule")

    existing = db.scalar(
        select(FeedConsumptionRecord.id).where(
            FeedConsumptionRecord.farm_id == farm_id,
            FeedConsumptionRecord.client_request_id == client_request_id,
        )
    )
    if existing is not None:
        raise FeedValidationError("Duplicate feeding record")

    apply_stock_movement(
        db,
        farm_id=farm_id,
        feed_item_id=feed_item_id,
        client_request_id=client_request_id,
        movement_type=StockMovementType.CONSUMPTION,
        quantity=quantity,
        unit=unit,
        actor_id=actor_id,
        reason="Daily feeding consumption",
        occurred_at=datetime.now(timezone.utc),
    )
    record = FeedConsumptionRecord(
        farm_id=farm_id,
        client_request_id=client_request_id,
        feed_item_id=feed_item_id,
        schedule_id=schedule_id,
        target_type=target_type,
        cattle_id=cattle_id,
        group_name=group_name,
        head_count=head_count,
        feeding_date=feeding_date,
        quantity=quantity,
        unit=unit,
        notes=notes,
        recorded_by_id=actor_id,
    )
    db.add(record)
    return record
