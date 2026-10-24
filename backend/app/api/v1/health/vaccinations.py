from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import (
    require_farm_permission,
    require_veterinarian_permission,
)
from app.api.v1.auth import get_current_user
from app.api.v1.health.dependencies import (
    HEALTH_PREFIX,
    commit_or_error,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.health import (
    VaccinationAdministration,
    VaccinationSchedule,
    VaccinationScheduleStatus,
)
from app.models.user import User
from app.schemas.health import (
    VaccinationAdministrationCreate,
    VaccinationAdministrationResponse,
    VaccinationScheduleCreate,
    VaccinationScheduleResponse,
    VaccinationScheduleUpdate,
)
from app.services.health import (
    HealthValidationError,
    add_audit_event,
    cattle_for_health_action,
    scoped_record,
    serializable_snapshot,
    validate_active_member,
    validate_event_time,
)


router = APIRouter(prefix=HEALTH_PREFIX)


@router.post(
    "/vaccination-schedules",
    response_model=VaccinationScheduleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_vaccination_schedule(
    farm_id: UUID,
    data: VaccinationScheduleCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VACCINATION_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        cattle_for_health_action(
            db, farm_id=farm_id, cattle_id=data.cattle_id
        )
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.responsible_user_id,
            field_name="responsible_user_id",
        )
    except HealthValidationError as error:
        raise validation_error(error) from None
    schedule = VaccinationSchedule(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        vaccine_name=data.vaccine_name,
        scheduled_date=data.scheduled_date,
        due_date=data.due_date,
        responsible_user_id=data.responsible_user_id,
        notes=data.notes,
        created_by_id=current_user.id,
    )
    db.add(schedule)
    commit_or_error(
        db,
        conflict_detail="An active matching vaccination schedule already exists",
        server_detail="Could not create vaccination schedule",
    )
    db.refresh(schedule)
    return schedule


@router.get(
    "/vaccination-schedules",
    response_model=list[VaccinationScheduleResponse],
)
def list_vaccination_schedules(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    schedule_status: VaccinationScheduleStatus | None = Query(
        default=None, alias="status"
    ),
    due_from: date | None = None,
    due_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if due_from and due_to and due_from > due_to:
        raise HTTPException(status_code=422, detail="due_from cannot exceed due_to")
    statement = select(VaccinationSchedule).where(
        VaccinationSchedule.farm_id == farm_id
    )
    if cattle_id:
        statement = statement.where(
            VaccinationSchedule.cattle_id == cattle_id
        )
    if schedule_status:
        statement = statement.where(
            VaccinationSchedule.status == schedule_status
        )
    if due_from:
        statement = statement.where(VaccinationSchedule.due_date >= due_from)
    if due_to:
        statement = statement.where(VaccinationSchedule.due_date <= due_to)
    return list(
        db.scalars(
            statement.order_by(
                VaccinationSchedule.due_date, VaccinationSchedule.id
            )
            .limit(limit)
            .offset(offset)
        )
    )


@router.patch(
    "/vaccination-schedules/{schedule_id}",
    response_model=VaccinationScheduleResponse,
)
def update_vaccination_schedule(
    farm_id: UUID,
    schedule_id: UUID,
    data: VaccinationScheduleUpdate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VACCINATION_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    schedule = scoped_record(
        db,
        VaccinationSchedule,
        farm_id=farm_id,
        record_id=schedule_id,
        lock=True,
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Vaccination schedule not found")
    if schedule.status != VaccinationScheduleStatus.SCHEDULED:
        raise HTTPException(
            status_code=409, detail="Only scheduled vaccinations can be changed"
        )
    values = data.model_dump(exclude_unset=True)
    prospective_scheduled = values.get(
        "scheduled_date", schedule.scheduled_date
    )
    prospective_due = values.get("due_date", schedule.due_date)
    if prospective_due < prospective_scheduled:
        raise HTTPException(
            status_code=422, detail="due_date cannot predate scheduled_date"
        )
    try:
        if "responsible_user_id" in values:
            validate_active_member(
                db,
                farm_id=farm_id,
                user_id=data.responsible_user_id,
                field_name="responsible_user_id",
            )
    except HealthValidationError as error:
        raise validation_error(error) from None
    previous = serializable_snapshot(schedule)
    schedule.scheduled_date = prospective_scheduled
    schedule.due_date = prospective_due
    if "responsible_user_id" in values:
        schedule.responsible_user_id = data.responsible_user_id
    if "notes" in values:
        schedule.notes = data.notes
    action = "RESCHEDULED"
    if data.status == "CANCELLED":
        schedule.status = VaccinationScheduleStatus.CANCELLED
        schedule.cancelled_at = datetime.now(timezone.utc)
        schedule.cancellation_reason = data.reason
        action = "CANCELLED"
    add_audit_event(
        db,
        farm_id=farm_id,
        cattle_id=schedule.cattle_id,
        record_type="VACCINATION_SCHEDULE",
        record_id=schedule.id,
        action=action,
        reason=data.reason,
        actor_id=current_user.id,
        previous_data=previous,
        replacement_data={
            "scheduled_date": str(schedule.scheduled_date),
            "due_date": str(schedule.due_date),
            "status": schedule.status.value,
        },
    )
    commit_or_error(
        db,
        conflict_detail="Vaccination schedule update conflicts with existing data",
        server_detail="Could not update vaccination schedule",
    )
    db.refresh(schedule)
    return schedule


@router.post(
    "/vaccination-administrations",
    response_model=VaccinationAdministrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def administer_vaccination(
    farm_id: UUID,
    data: VaccinationAdministrationCreate,
    access: FarmAccess = Depends(
        require_veterinarian_permission(
            Permission.HEALTH_VACCINATION_ADMINISTER
        )
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        animal = cattle_for_health_action(
            db, farm_id=farm_id, cattle_id=data.cattle_id
        )
        validate_event_time(
            animal, data.administered_at, field_name="administered_at"
        )
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.administered_by_id,
            field_name="administered_by_id",
        )
    except HealthValidationError as error:
        raise validation_error(error) from None
    schedule = None
    if data.schedule_id:
        schedule = scoped_record(
            db,
            VaccinationSchedule,
            farm_id=farm_id,
            cattle_id=data.cattle_id,
            record_id=data.schedule_id,
            lock=True,
        )
        if schedule is None:
            raise HTTPException(status_code=404, detail="Vaccination schedule not found")
        if schedule.status != VaccinationScheduleStatus.SCHEDULED:
            raise HTTPException(
                status_code=409, detail="Vaccination schedule is not active"
            )
        if schedule.vaccine_name.casefold() != data.vaccine_name.casefold():
            raise HTTPException(
                status_code=422,
                detail="Administration vaccine must match the schedule",
            )
        if data.administered_at.date() < schedule.scheduled_date:
            raise HTTPException(
                status_code=422,
                detail="Administration cannot predate the scheduled date",
            )
    administration = VaccinationAdministration(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        schedule_id=data.schedule_id,
        vaccine_name=data.vaccine_name,
        administered_at=data.administered_at,
        dose=data.dose,
        dose_unit=data.dose_unit,
        route=data.route,
        batch_lot_number=data.batch_lot_number,
        expiry_date=data.expiry_date,
        administered_by_id=data.administered_by_id,
        notes=data.notes,
        follow_up_due_at=data.follow_up_due_at,
        next_due_date=data.next_due_date,
        created_by_id=current_user.id,
    )
    db.add(administration)
    if schedule:
        previous = serializable_snapshot(schedule)
        schedule.status = VaccinationScheduleStatus.COMPLETED
        schedule.completed_at = data.administered_at
        add_audit_event(
            db,
            farm_id=farm_id,
            cattle_id=data.cattle_id,
            record_type="VACCINATION_SCHEDULE",
            record_id=schedule.id,
            action="COMPLETED",
            reason="Vaccination administration recorded",
            actor_id=current_user.id,
            previous_data=previous,
        )
    commit_or_error(
        db,
        conflict_detail="This vaccination administration is already recorded",
        server_detail="Could not record vaccination administration",
    )
    db.refresh(administration)
    return administration


@router.get(
    "/vaccination-administrations",
    response_model=list[VaccinationAdministrationResponse],
)
def list_vaccination_administrations(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    administered_from: datetime | None = None,
    administered_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if (
        administered_from
        and administered_to
        and administered_from > administered_to
    ):
        raise HTTPException(
            status_code=422,
            detail="administered_from cannot be after administered_to",
        )
    statement = select(VaccinationAdministration).where(
        VaccinationAdministration.farm_id == farm_id
    )
    if cattle_id:
        statement = statement.where(
            VaccinationAdministration.cattle_id == cattle_id
        )
    if administered_from:
        statement = statement.where(
            VaccinationAdministration.administered_at >= administered_from
        )
    if administered_to:
        statement = statement.where(
            VaccinationAdministration.administered_at <= administered_to
        )
    return list(
        db.scalars(
            statement.order_by(
                VaccinationAdministration.administered_at.desc(),
                VaccinationAdministration.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )
