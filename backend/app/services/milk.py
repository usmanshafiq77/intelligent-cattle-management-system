import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import Numeric, cast, func, select
from sqlalchemy.orm import Session

from app.models.cattle import AnimalCategory, AnimalSex, Cattle, CattleStatus
from app.models.farm_member import FarmMember, MemberStatus
from app.models.milk import (
    LactationStatus,
    MilkCorrectionTarget,
    MilkLactation,
    MilkQualityMeasurement,
    MilkRecordCorrection,
    MilkingSession,
)


class MilkValidationError(ValueError):
    pass


FINAL_CATTLE_STATUSES = {
    CattleStatus.SOLD,
    CattleStatus.DECEASED,
    CattleStatus.TRANSFERRED,
    CattleStatus.ARCHIVED,
}


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def eligible_cattle(db: Session, *, farm_id: UUID, cattle_id: UUID) -> Cattle:
    animal = db.scalar(
        select(Cattle).where(Cattle.id == cattle_id, Cattle.farm_id == farm_id)
    )
    if animal is None:
        raise MilkValidationError("Cattle not found")
    if animal.sex != AnimalSex.FEMALE or animal.category != AnimalCategory.COW:
        raise MilkValidationError("Milk production requires a female COW")
    if animal.status in FINAL_CATTLE_STATUSES:
        raise MilkValidationError(
            f"New milk actions are not allowed for {animal.status.value} cattle"
        )
    return animal


def validate_member(db: Session, *, farm_id: UUID, user_id: UUID | None) -> None:
    if user_id is None:
        return
    member = db.scalar(
        select(FarmMember.id).where(
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == user_id,
            FarmMember.status == MemberStatus.ACTIVE,
        )
    )
    if member is None:
        raise MilkValidationError("operator_id must identify an active farm member")


def scoped_lactation(
    db: Session, *, farm_id: UUID, lactation_id: UUID, cattle_id: UUID | None = None,
    lock: bool = False,
) -> MilkLactation | None:
    query = select(MilkLactation).where(
        MilkLactation.id == lactation_id, MilkLactation.farm_id == farm_id
    )
    if cattle_id is not None:
        query = query.where(MilkLactation.cattle_id == cattle_id)
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def scoped_session(
    db: Session, *, farm_id: UUID, session_id: UUID, cattle_id: UUID | None = None,
    lock: bool = False,
) -> MilkingSession | None:
    query = select(MilkingSession).where(
        MilkingSession.id == session_id, MilkingSession.farm_id == farm_id
    )
    if cattle_id is not None:
        query = query.where(MilkingSession.cattle_id == cattle_id)
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def validate_lactation_dates(
    db: Session, *, farm_id: UUID, cattle_id: UUID, start_date: date,
    end_date: date | None = None, exclude_id: UUID | None = None,
) -> None:
    query = select(MilkLactation).where(
        MilkLactation.farm_id == farm_id,
        MilkLactation.cattle_id == cattle_id,
        MilkLactation.start_date <= (end_date or date.max),
        func.coalesce(MilkLactation.end_date, date.max) >= start_date,
    )
    if exclude_id:
        query = query.where(MilkLactation.id != exclude_id)
    if db.scalar(query.limit(1)) is not None:
        raise MilkValidationError("Lactation period overlaps an existing lactation")


def validate_session_for_create(
    db: Session, *, farm_id: UUID, cattle_id: UUID, lactation_id: UUID,
    milking_date: date, operator_id: UUID | None,
) -> tuple[Cattle, MilkLactation]:
    animal = eligible_cattle(db, farm_id=farm_id, cattle_id=cattle_id)
    lactation = scoped_lactation(
        db, farm_id=farm_id, lactation_id=lactation_id, cattle_id=cattle_id
    )
    if lactation is None:
        raise MilkValidationError("Lactation not found")
    if milking_date < lactation.start_date:
        raise MilkValidationError("milking_date cannot predate lactation")
    boundary = lactation.end_date or lactation.dry_off_date
    if boundary and milking_date > boundary:
        raise MilkValidationError("milking_date is outside the lactation period")
    if milking_date > utc_today():
        raise MilkValidationError("milking_date cannot be in the future")
    if animal.date_of_birth and milking_date < animal.date_of_birth:
        raise MilkValidationError("milking_date cannot predate birth")
    validate_member(db, farm_id=farm_id, user_id=operator_id)
    return animal, lactation


def snapshot(record: Any, fields: set[str] | None = None) -> dict[str, Any]:
    return {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
        if fields is None or column.name in fields
    }


def latest_correction(
    db: Session, *, farm_id: UUID, target_type: MilkCorrectionTarget, target_id: UUID
) -> MilkRecordCorrection | None:
    return db.scalar(
        select(MilkRecordCorrection)
        .where(
            MilkRecordCorrection.farm_id == farm_id,
            MilkRecordCorrection.target_type == target_type,
            MilkRecordCorrection.target_id == target_id,
        )
        .order_by(MilkRecordCorrection.created_at.desc(), MilkRecordCorrection.id.desc())
        .limit(1)
    )


def effective_session(db: Session, record: MilkingSession) -> dict[str, Any]:
    correction = latest_correction(
        db, farm_id=record.farm_id, target_type=MilkCorrectionTarget.SESSION,
        target_id=record.id,
    )
    values = snapshot(record)
    if correction:
        values.update(correction.replacement_values)
    values["effective_volume_liters"] = Decimal(str(values["volume_liters"]))
    values["effective_notes"] = values.get("notes")
    return values


def effective_quality(db: Session, record: MilkQualityMeasurement) -> dict[str, Any]:
    correction = latest_correction(
        db, farm_id=record.farm_id, target_type=MilkCorrectionTarget.QUALITY,
        target_id=record.id,
    )
    values = snapshot(record)
    if correction:
        values.update(correction.replacement_values)
    values["effective_values"] = {
        key: values.get(key)
        for key in QUALITY_CORRECTABLE_FIELDS
        if values.get(key) is not None
    }
    return values


SESSION_CORRECTABLE_FIELDS = {"volume_liters", "notes"}
QUALITY_CORRECTABLE_FIELDS = {
    "fat_percent", "snf_percent", "protein_percent", "density",
    "temperature_celsius", "somatic_cell_count", "notes",
}


def validate_correction_values(
    target_type: MilkCorrectionTarget, replacements: dict[str, Any]
) -> dict[str, Any]:
    allowed = (
        SESSION_CORRECTABLE_FIELDS
        if target_type == MilkCorrectionTarget.SESSION
        else QUALITY_CORRECTABLE_FIELDS
    )
    if not replacements or set(replacements) - allowed:
        raise MilkValidationError(
            "Correction contains unsupported or identity-changing fields"
        )
    cleaned = dict(replacements)
    decimal_fields = allowed - {"notes", "somatic_cell_count"}
    for field in decimal_fields & cleaned.keys():
        if cleaned[field] is None and field == "volume_liters":
            raise MilkValidationError("volume_liters cannot be null")
        if cleaned[field] is not None:
            try:
                value = Decimal(str(cleaned[field]))
            except InvalidOperation as error:
                raise MilkValidationError(f"{field} must be numeric") from error
            if field == "volume_liters" and value < 0:
                raise MilkValidationError("volume_liters cannot be negative")
            if field in {"fat_percent", "snf_percent", "protein_percent"} and not 0 <= value <= 100:
                raise MilkValidationError(f"{field} must be between 0 and 100")
            if field == "density" and value <= 0:
                raise MilkValidationError("density must be positive")
            if field == "temperature_celsius" and value < Decimal("-273.15"):
                raise MilkValidationError("temperature_celsius is below absolute zero")
            cleaned[field] = str(value)
    if "somatic_cell_count" in cleaned and cleaned["somatic_cell_count"] is not None:
        try:
            cleaned["somatic_cell_count"] = int(cleaned["somatic_cell_count"])
        except (TypeError, ValueError) as error:
            raise MilkValidationError("somatic_cell_count must be an integer") from error
        if cleaned["somatic_cell_count"] < 0:
            raise MilkValidationError("somatic_cell_count cannot be negative")
    if "notes" in cleaned and cleaned["notes"] is not None:
        cleaned["notes"] = " ".join(str(cleaned["notes"]).split()) or None
    return cleaned


def effective_volume_expression():
    corrected = (
        select(MilkRecordCorrection.replacement_values["volume_liters"].astext)
        .where(
            MilkRecordCorrection.farm_id == MilkingSession.farm_id,
            MilkRecordCorrection.target_type == MilkCorrectionTarget.SESSION,
            MilkRecordCorrection.target_id == MilkingSession.id,
            MilkRecordCorrection.replacement_values.has_key("volume_liters"),  # noqa: W601
        )
        .order_by(MilkRecordCorrection.created_at.desc(), MilkRecordCorrection.id.desc())
        .limit(1)
        .correlate(MilkingSession)
        .scalar_subquery()
    )
    return func.coalesce(cast(corrected, Numeric(12, 3)), MilkingSession.volume_liters)
