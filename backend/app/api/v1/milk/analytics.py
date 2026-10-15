from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.milk.dependencies import MILK_PREFIX
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import Cattle
from app.models.milk import MilkLactation, MilkQualityMeasurement, MilkingSession
from app.schemas.milk import (
    AnimalProductionTotal, MilkDatasetRow, ProductionBreakdown,
    ProductionBucket, ProductionSummary, SessionTotal,
)
from app.services.milk import effective_quality, effective_session


router = APIRouter(prefix=f"{MILK_PREFIX}/analytics")


def _validated_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from cannot be after date_to")
    if (date_to - date_from).days > 3660:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 10 years")


def _period_start(day: date, interval: str) -> date:
    if interval == "daily":
        return day
    if interval == "weekly":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def _effective_rows(
    db: Session, farm_id: UUID, date_from: date, date_to: date,
    cattle_id: UUID | None = None,
) -> list[dict]:
    query = select(MilkingSession).where(
        MilkingSession.farm_id == farm_id,
        MilkingSession.milking_date >= date_from,
        MilkingSession.milking_date <= date_to,
    )
    if cattle_id:
        query = query.where(MilkingSession.cattle_id == cattle_id)
    return [effective_session(db, row) for row in db.scalars(query)]


@router.get("/production", response_model=ProductionSummary)
def production_summary(
    farm_id: UUID, date_from: date, date_to: date,
    interval: Literal["daily", "weekly", "monthly"] = "daily",
    cattle_id: UUID | None = None,
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_ANALYTICS_VIEW)),
    db: Session = Depends(get_db),
):
    _validated_range(date_from, date_to)
    rows = _effective_rows(db, farm_id, date_from, date_to, cattle_id)
    totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    animals: dict[date, set[UUID]] = defaultdict(set)
    counts: dict[date, int] = defaultdict(int)
    all_animals: set[UUID] = set()
    total = Decimal("0")
    for row in rows:
        key = _period_start(row["milking_date"], interval)
        volume = Decimal(str(row["effective_volume_liters"]))
        totals[key] += volume
        animals[key].add(row["cattle_id"])
        counts[key] += 1
        all_animals.add(row["cattle_id"])
        total += volume
    buckets = [
        ProductionBucket(
            period_start=key, volume_liters=totals[key],
            recorded_animals=len(animals[key]), record_count=counts[key],
        )
        for key in sorted(totals)
    ]
    return ProductionSummary(
        date_from=date_from, date_to=date_to, total_volume_liters=total,
        recorded_animals=len(all_animals), record_count=len(rows),
        average_per_recorded_animal_liters=(total / len(all_animals) if all_animals else None),
        buckets=buckets,
    )


@router.get("/breakdown", response_model=ProductionBreakdown)
def production_breakdown(
    farm_id: UUID, date_from: date, date_to: date,
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_ANALYTICS_VIEW)),
    db: Session = Depends(get_db),
):
    _validated_range(date_from, date_to)
    rows = _effective_rows(db, farm_id, date_from, date_to)
    by_session: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    by_animal: dict[UUID, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        value = Decimal(str(row["effective_volume_liters"]))
        by_session[row["session_kind"].value] += value
        by_animal[row["cattle_id"]] += value
    animal_totals = sorted(
        [AnimalProductionTotal(cattle_id=key, volume_liters=value) for key, value in by_animal.items()],
        key=lambda item: (item.volume_liters, str(item.cattle_id)), reverse=True,
    )
    return ProductionBreakdown(
        session_totals=[SessionTotal(session_kind=key, volume_liters=value) for key, value in sorted(by_session.items())],
        animal_totals=animal_totals,
        highest_producing=animal_totals[0] if animal_totals else None,
        lowest_producing=animal_totals[-1] if animal_totals else None,
    )


@router.get("/dataset", response_model=list[MilkDatasetRow])
def milk_dataset(
    farm_id: UUID, date_from: date, date_to: date,
    limit: int = Query(default=1000, ge=1, le=5000), offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(require_farm_permission(Permission.MILK_ANALYTICS_VIEW)),
    db: Session = Depends(get_db),
):
    _validated_range(date_from, date_to)
    records = db.execute(
        select(MilkingSession, MilkLactation, Cattle)
        .join(MilkLactation, MilkLactation.id == MilkingSession.lactation_id)
        .join(Cattle, Cattle.id == MilkingSession.cattle_id)
        .where(
            MilkingSession.farm_id == farm_id,
            MilkingSession.milking_date >= date_from,
            MilkingSession.milking_date <= date_to,
        )
        .order_by(MilkingSession.milking_date, MilkingSession.id)
        .limit(limit).offset(offset)
    )
    output = []
    for session, lactation, animal in records:
        effective = effective_session(db, session)
        quality = db.scalar(
            select(MilkQualityMeasurement)
            .where(MilkQualityMeasurement.session_id == session.id)
            .order_by(MilkQualityMeasurement.tested_at.desc()).limit(1)
        )
        quality_values = effective_quality(db, quality)["effective_values"] if quality else {}
        output.append(MilkDatasetRow(
            cattle_id=animal.id, species=animal.species.value, breed_id=animal.breed_id,
            date_of_birth=animal.date_of_birth, lactation_number=lactation.sequence_number,
            milking_date=session.milking_date,
            days_in_milk=(session.milking_date - lactation.start_date).days,
            session_kind=session.session_kind,
            volume_liters=effective["effective_volume_liters"],
            fat_percent=quality_values.get("fat_percent"),
            snf_percent=quality_values.get("snf_percent"),
            protein_percent=quality_values.get("protein_percent"),
            observation_complete=quality is not None,
        ))
    return output
