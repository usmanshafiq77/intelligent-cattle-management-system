from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.feed import (
    FeedConsumptionRecord,
    FeedItem,
    FeedStockMovement,
    FeedingSchedule,
    NutritionPlan,
    NutritionPlanItem,
    NutritionPlanStatus,
    StockMovementType,
)
from app.models.user import User
from app.schemas.feed import (
    FeedConsumptionCreate,
    FeedConsumptionResponse,
    FeedCostSummary,
    FeedItemCreate,
    FeedItemResponse,
    FeedItemUpdate,
    FeedReportSummary,
    FeedingScheduleCreate,
    FeedingScheduleResponse,
    FeedingScheduleUpdate,
    LowStockAlert,
    NutritionPlanCreate,
    NutritionPlanResponse,
    NutritionPlanUpdate,
    PurchaseCreate,
    PurchaseResponse,
    StockAdjustmentCreate,
    StockMovementResponse,
)
from app.services.feed import (
    FeedValidationError,
    apply_stock_movement,
    normalize_name,
    record_consumption,
    scoped_feed_item,
    scoped_schedule,
    validate_cattle_target,
    validate_item_unit,
)
from app.services.finance import post_feed_purchase


router = APIRouter(
    prefix="/farms/{farm_id}/feed",
    tags=["Feed and Nutrition Management"],
)


def _validation_error(error: FeedValidationError) -> HTTPException:
    detail = str(error)
    status_code = status.HTTP_409_CONFLICT if (
        "Duplicate" in detail or "Insufficient" in detail
    ) else status.HTTP_422_UNPROCESSABLE_CONTENT
    return HTTPException(status_code=status_code, detail=detail)


def _commit(db: Session, *, conflict: str, failure: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail=failure) from None


def _item_response(item: FeedItem) -> FeedItemResponse:
    response = FeedItemResponse.model_validate(item)
    return response.model_copy(
        update={
            "low_stock": item.reorder_level > 0
            and item.current_quantity <= item.reorder_level
        }
    )


def _plan_response(db: Session, plan: NutritionPlan) -> NutritionPlanResponse:
    lines = list(
        db.scalars(
            select(NutritionPlanItem)
            .where(
                NutritionPlanItem.farm_id == plan.farm_id,
                NutritionPlanItem.plan_id == plan.id,
            )
            .order_by(NutritionPlanItem.id)
        )
    )
    return NutritionPlanResponse.model_validate(
        {
            "id": plan.id,
            "farm_id": plan.farm_id,
            "name": plan.name,
            "target_type": plan.target_type,
            "cattle_id": plan.cattle_id,
            "group_name": plan.group_name,
            "objective": plan.objective,
            "notes": plan.notes,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "status": plan.status,
            "professional_review_required": plan.professional_review_required,
            "created_by_id": plan.created_by_id,
            "reviewed_by_id": plan.reviewed_by_id,
            "reviewed_at": plan.reviewed_at,
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
            "lines": lines,
        }
    )


@router.get("/items", response_model=list[FeedItemResponse])
def list_feed_items(
    farm_id: UUID,
    include_inactive: bool = False,
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_VIEW)),
    db: Session = Depends(get_db),
):
    query = select(FeedItem).where(FeedItem.farm_id == farm_id)
    if not include_inactive:
        query = query.where(FeedItem.is_active.is_(True))
    records = db.scalars(query.order_by(FeedItem.name, FeedItem.id))
    return [_item_response(item) for item in records]


@router.post("/items", response_model=FeedItemResponse, status_code=201)
def create_feed_item(
    farm_id: UUID,
    data: FeedItemCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_INVENTORY_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = FeedItem(
        farm_id=farm_id,
        name=data.name,
        normalized_name=normalize_name(data.name),
        category=data.category,
        unit=data.unit,
        reorder_level=data.reorder_level,
        description=data.description,
        created_by_id=current_user.id,
    )
    db.add(record)
    _commit(db, conflict="A feed item with this name already exists", failure="Could not create feed item")
    db.refresh(record)
    return _item_response(record)


@router.patch("/items/{feed_item_id}", response_model=FeedItemResponse)
def update_feed_item(
    farm_id: UUID,
    feed_item_id: UUID,
    data: FeedItemUpdate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_INVENTORY_MANAGE)
    ),
    db: Session = Depends(get_db),
):
    record = scoped_feed_item(db, farm_id=farm_id, feed_item_id=feed_item_id, lock=True)
    if record is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("is_active") is False:
        active_schedule = db.scalar(
            select(FeedingSchedule.id).where(
                FeedingSchedule.farm_id == farm_id,
                FeedingSchedule.feed_item_id == feed_item_id,
                FeedingSchedule.is_active.is_(True),
            )
        )
        if active_schedule is not None:
            raise HTTPException(status_code=409, detail="Deactivate feeding schedules before this feed item")
    for field, value in changes.items():
        setattr(record, field, value)
    if "name" in changes:
        record.normalized_name = normalize_name(record.name)
    _commit(db, conflict="A feed item with this name already exists", failure="Could not update feed item")
    db.refresh(record)
    return _item_response(record)


@router.post("/stock/purchases", response_model=PurchaseResponse, status_code=201)
def record_purchase(
    farm_id: UUID,
    data: PurchaseCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_INVENTORY_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        movement = apply_stock_movement(
            db,
            farm_id=farm_id,
            feed_item_id=data.feed_item_id,
            client_request_id=data.client_request_id,
            movement_type=StockMovementType.PURCHASE,
            quantity=data.quantity,
            unit=data.unit,
            actor_id=current_user.id,
            reason="Feed stock purchase",
            occurred_at=data.occurred_at,
            unit_cost=data.unit_cost,
            currency=data.currency,
            supplier=data.supplier,
            reference=data.reference,
        )
        db.flush()
        post_feed_purchase(db, movement, current_user.id)
    except FeedValidationError as error:
        db.rollback()
        raise _validation_error(error) from None
    _commit(db, conflict="Duplicate or invalid feed purchase", failure="Could not record feed purchase")
    db.refresh(movement)
    return PurchaseResponse.model_validate(
        {**movement.__dict__, "total_cost": movement.quantity * movement.unit_cost}
    )


@router.get("/stock/purchases", response_model=list[PurchaseResponse])
def list_purchases(
    farm_id: UUID,
    limit: int = Query(default=100, ge=1, le=500),
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_COST_VIEW)),
    db: Session = Depends(get_db),
):
    records = db.scalars(
        select(FeedStockMovement)
        .where(
            FeedStockMovement.farm_id == farm_id,
            FeedStockMovement.movement_type == StockMovementType.PURCHASE,
        )
        .order_by(FeedStockMovement.occurred_at.desc(), FeedStockMovement.id.desc())
        .limit(limit)
    )
    return [
        PurchaseResponse.model_validate(
            {**record.__dict__, "total_cost": record.quantity * record.unit_cost}
        )
        for record in records
    ]


@router.post("/stock/adjustments", response_model=StockMovementResponse, status_code=201)
def adjust_stock(
    farm_id: UUID,
    data: StockAdjustmentCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_INVENTORY_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    movement_type = (
        StockMovementType.ADJUSTMENT_IN
        if data.direction == "IN"
        else StockMovementType.ADJUSTMENT_OUT
    )
    try:
        movement = apply_stock_movement(
            db,
            farm_id=farm_id,
            feed_item_id=data.feed_item_id,
            client_request_id=data.client_request_id,
            movement_type=movement_type,
            quantity=data.quantity,
            unit=data.unit,
            actor_id=current_user.id,
            reason=data.reason,
            occurred_at=data.occurred_at,
            reference=data.reference,
        )
    except FeedValidationError as error:
        db.rollback()
        raise _validation_error(error) from None
    _commit(db, conflict="Duplicate or invalid stock adjustment", failure="Could not adjust feed stock")
    db.refresh(movement)
    return movement


@router.get("/stock/history", response_model=list[StockMovementResponse])
def stock_history(
    farm_id: UUID,
    feed_item_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_VIEW)),
    db: Session = Depends(get_db),
):
    query = select(FeedStockMovement).where(FeedStockMovement.farm_id == farm_id)
    if feed_item_id is not None:
        query = query.where(FeedStockMovement.feed_item_id == feed_item_id)
    return list(db.scalars(query.order_by(FeedStockMovement.occurred_at.desc()).limit(limit)))


@router.get("/alerts/low-stock", response_model=list[LowStockAlert])
def low_stock_alerts(
    farm_id: UUID,
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_VIEW)),
    db: Session = Depends(get_db),
):
    records = db.scalars(
        select(FeedItem).where(
            FeedItem.farm_id == farm_id,
            FeedItem.is_active.is_(True),
            FeedItem.reorder_level > 0,
            FeedItem.current_quantity <= FeedItem.reorder_level,
        ).order_by(FeedItem.current_quantity)
    )
    return [
        LowStockAlert(
            feed_item_id=item.id,
            name=item.name,
            unit=item.unit,
            current_quantity=item.current_quantity,
            reorder_level=item.reorder_level,
            shortage_quantity=max(item.reorder_level - item.current_quantity, Decimal("0")),
        )
        for item in records
    ]


@router.get("/schedules", response_model=list[FeedingScheduleResponse])
def list_schedules(
    farm_id: UUID,
    active_only: bool = True,
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_VIEW)),
    db: Session = Depends(get_db),
):
    query = select(FeedingSchedule).where(FeedingSchedule.farm_id == farm_id)
    if active_only:
        query = query.where(FeedingSchedule.is_active.is_(True))
    return list(db.scalars(query.order_by(FeedingSchedule.feeding_time, FeedingSchedule.name)))


@router.post("/schedules", response_model=FeedingScheduleResponse, status_code=201)
def create_schedule(
    farm_id: UUID,
    data: FeedingScheduleCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_SCHEDULE_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = scoped_feed_item(db, farm_id=farm_id, feed_item_id=data.feed_item_id)
    if item is None:
        raise HTTPException(status_code=422, detail="Feed item not found")
    try:
        validate_item_unit(item, data.unit)
        validate_cattle_target(db, farm_id=farm_id, target_type=data.target_type, cattle_id=data.cattle_id)
    except FeedValidationError as error:
        raise _validation_error(error) from None
    record = FeedingSchedule(
        farm_id=farm_id,
        normalized_name=normalize_name(data.name),
        created_by_id=current_user.id,
        **data.model_dump(),
    )
    db.add(record)
    _commit(db, conflict="A feeding schedule with this name already exists", failure="Could not create feeding schedule")
    db.refresh(record)
    return record


@router.patch("/schedules/{schedule_id}", response_model=FeedingScheduleResponse)
def update_schedule(
    farm_id: UUID,
    schedule_id: UUID,
    data: FeedingScheduleUpdate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_SCHEDULE_MANAGE)
    ),
    db: Session = Depends(get_db),
):
    record = scoped_schedule(db, farm_id=farm_id, schedule_id=schedule_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Feeding schedule not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    if record.end_date is not None and record.end_date < record.start_date:
        raise HTTPException(status_code=422, detail="end_date cannot precede start_date")
    _commit(db, conflict="Invalid feeding schedule update", failure="Could not update feeding schedule")
    db.refresh(record)
    return record


@router.get("/consumption", response_model=list[FeedConsumptionResponse])
def list_consumption(
    farm_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_VIEW)),
    db: Session = Depends(get_db),
):
    query = select(FeedConsumptionRecord).where(FeedConsumptionRecord.farm_id == farm_id)
    if date_from is not None:
        query = query.where(FeedConsumptionRecord.feeding_date >= date_from)
    if date_to is not None:
        query = query.where(FeedConsumptionRecord.feeding_date <= date_to)
    return list(db.scalars(query.order_by(FeedConsumptionRecord.feeding_date.desc()).limit(limit)))


@router.post("/consumption", response_model=FeedConsumptionResponse, status_code=201)
def create_consumption(
    farm_id: UUID,
    data: FeedConsumptionCreate,
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_RECORD)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        record = record_consumption(
            db,
            farm_id=farm_id,
            actor_id=current_user.id,
            **data.model_dump(),
        )
    except FeedValidationError as error:
        db.rollback()
        raise _validation_error(error) from None
    _commit(db, conflict="Duplicate or invalid feeding record", failure="Could not record feed consumption")
    db.refresh(record)
    return record


@router.get("/nutrition-plans", response_model=list[NutritionPlanResponse])
def list_nutrition_plans(
    farm_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_NUTRITION_VIEW)
    ),
    db: Session = Depends(get_db),
):
    plans = db.scalars(
        select(NutritionPlan)
        .where(NutritionPlan.farm_id == farm_id)
        .order_by(NutritionPlan.start_date.desc(), NutritionPlan.name)
    )
    return [_plan_response(db, plan) for plan in plans]


@router.post("/nutrition-plans", response_model=NutritionPlanResponse, status_code=201)
def create_nutrition_plan(
    farm_id: UUID,
    data: NutritionPlanCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_NUTRITION_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        validate_cattle_target(db, farm_id=farm_id, target_type=data.target_type, cattle_id=data.cattle_id)
        for line in data.lines:
            item = scoped_feed_item(db, farm_id=farm_id, feed_item_id=line.feed_item_id)
            if item is None:
                raise FeedValidationError("Nutrition plan feed item not found")
            validate_item_unit(item, line.unit)
    except FeedValidationError as error:
        raise _validation_error(error) from None

    plan = NutritionPlan(
        farm_id=farm_id,
        name=data.name,
        normalized_name=normalize_name(data.name),
        target_type=data.target_type,
        cattle_id=data.cattle_id,
        group_name=data.group_name,
        objective=data.objective,
        notes=data.notes,
        start_date=data.start_date,
        end_date=data.end_date,
        created_by_id=current_user.id,
    )
    db.add(plan)
    try:
        db.flush()
        for line in data.lines:
            db.add(
                NutritionPlanItem(
                    farm_id=farm_id,
                    plan_id=plan.id,
                    **line.model_dump(),
                )
            )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate nutrition plan or feed line") from None
    _commit(db, conflict="Duplicate nutrition plan or feed line", failure="Could not create nutrition plan")
    db.refresh(plan)
    return _plan_response(db, plan)


@router.patch("/nutrition-plans/{plan_id}", response_model=NutritionPlanResponse)
def update_nutrition_plan_status(
    farm_id: UUID,
    plan_id: UUID,
    data: NutritionPlanUpdate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_NUTRITION_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = db.scalar(
        select(NutritionPlan).where(
            NutritionPlan.id == plan_id,
            NutritionPlan.farm_id == farm_id,
        ).with_for_update()
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="Nutrition plan not found")
    if plan.status == NutritionPlanStatus.ARCHIVED:
        raise HTTPException(status_code=409, detail="Archived nutrition plans cannot be changed")
    plan.status = data.status
    if data.status == NutritionPlanStatus.REVIEWED:
        plan.reviewed_by_id = current_user.id
        plan.reviewed_at = datetime.now(timezone.utc)
    elif data.status == NutritionPlanStatus.DRAFT:
        plan.reviewed_by_id = None
        plan.reviewed_at = None
    _commit(db, conflict="Invalid nutrition plan transition", failure="Could not update nutrition plan")
    db.refresh(plan)
    return _plan_response(db, plan)


def _validate_report_range(date_from: date, date_to: date) -> None:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to cannot precede date_from")
    if (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="Report range cannot exceed 366 days")


@router.get("/reports/summary", response_model=FeedReportSummary)
def consumption_report(
    farm_id: UUID,
    date_from: date,
    date_to: date,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FEED_REPORTS_VIEW)
    ),
    db: Session = Depends(get_db),
):
    _validate_report_range(date_from, date_to)
    rows = db.execute(
        select(
            FeedConsumptionRecord.unit,
            func.sum(FeedConsumptionRecord.quantity),
            func.count(FeedConsumptionRecord.id),
        )
        .where(
            FeedConsumptionRecord.farm_id == farm_id,
            FeedConsumptionRecord.feeding_date >= date_from,
            FeedConsumptionRecord.feeding_date <= date_to,
        )
        .group_by(FeedConsumptionRecord.unit)
    )
    quantities: dict[str, Decimal] = {}
    record_count = 0
    for unit, quantity, count in rows:
        quantities[unit.value] = quantity
        record_count += count
    return FeedReportSummary(
        date_from=date_from,
        date_to=date_to,
        consumption_quantity_by_unit=quantities,
        consumption_records=record_count,
    )


@router.get("/reports/costs", response_model=FeedCostSummary)
def cost_report(
    farm_id: UUID,
    date_from: date,
    date_to: date,
    access: FarmAccess = Depends(require_farm_permission(Permission.FEED_COST_VIEW)),
    db: Session = Depends(get_db),
):
    _validate_report_range(date_from, date_to)
    start = datetime.combine(date_from, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(date_to, datetime.max.time(), tzinfo=timezone.utc)
    rows = db.execute(
        select(
            FeedStockMovement.currency,
            func.sum(FeedStockMovement.quantity * FeedStockMovement.unit_cost),
            func.count(FeedStockMovement.id),
        )
        .where(
            FeedStockMovement.farm_id == farm_id,
            FeedStockMovement.movement_type == StockMovementType.PURCHASE,
            FeedStockMovement.occurred_at >= start,
            FeedStockMovement.occurred_at <= end,
        )
        .group_by(FeedStockMovement.currency)
    )
    costs: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    purchase_count = 0
    for currency, amount, count in rows:
        costs[currency] += amount
        purchase_count += count
    return FeedCostSummary(
        date_from=date_from,
        date_to=date_to,
        purchase_cost_by_currency=dict(costs),
        purchase_count=purchase_count,
    )
