from datetime import datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.health.dependencies import HEALTH_PREFIX, commit_or_error
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.health import (
    HealthEncounter,
    HealthRecordCorrection,
    TreatmentPlan,
    TreatmentStatus,
    VaccinationAdministration,
    VaccinationSchedule,
    VaccinationScheduleStatus,
    VeterinaryVisit,
    VeterinaryVisitStatus,
)
from app.models.user import User
from app.schemas.health import (
    CorrectionCreate,
    CorrectionResponse,
    HealthReminderResponse,
)
from app.services.health import RECORD_MODELS, scoped_record, serializable_snapshot


router = APIRouter(prefix=HEALTH_PREFIX)


@router.post(
    "/corrections",
    response_model=CorrectionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_correction(
    farm_id: UUID,
    data: CorrectionCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_AUDIT_VIEW)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = RECORD_MODELS[data.record_type]
    record = scoped_record(
        db,
        model,
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        record_id=data.record_id,
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Health record not found")
    event = HealthRecordCorrection(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        record_type=data.record_type,
        record_id=data.record_id,
        action="CORRECTION_NOTED",
        reason=data.reason,
        correction_note=data.correction_note,
        previous_data=serializable_snapshot(record),
        replacement_data=data.replacement_data,
        actor_id=current_user.id,
    )
    db.add(event)
    commit_or_error(
        db,
        conflict_detail="Correction conflicts with current audit history",
        server_detail="Could not record health correction",
    )
    db.refresh(event)
    return event


@router.get("/corrections", response_model=list[CorrectionResponse])
def list_corrections(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    record_type: str | None = Query(default=None, max_length=50),
    record_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_AUDIT_VIEW)
    ),
    db: Session = Depends(get_db),
):
    statement = select(HealthRecordCorrection).where(
        HealthRecordCorrection.farm_id == farm_id
    )
    if cattle_id:
        statement = statement.where(
            HealthRecordCorrection.cattle_id == cattle_id
        )
    if record_type:
        statement = statement.where(
            HealthRecordCorrection.record_type == record_type
        )
    if record_id:
        statement = statement.where(
            HealthRecordCorrection.record_id == record_id
        )
    return list(
        db.scalars(
            statement.order_by(
                HealthRecordCorrection.created_at.desc(),
                HealthRecordCorrection.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/reminders", response_model=list[HealthReminderResponse])
def list_health_reminders(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    as_of: datetime | None = None,
    horizon_days: int = Query(default=30, ge=0, le=365),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    now = as_of or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise HTTPException(
            status_code=422, detail="as_of must include a timezone"
        )
    horizon = now + timedelta(days=horizon_days)
    items: list[HealthReminderResponse] = []

    def scoped(statement, model):
        statement = statement.where(model.farm_id == farm_id)
        return (
            statement.where(model.cattle_id == cattle_id)
            if cattle_id
            else statement
        )

    schedules = db.scalars(
        scoped(
            select(VaccinationSchedule).where(
                VaccinationSchedule.status
                == VaccinationScheduleStatus.SCHEDULED,
                VaccinationSchedule.due_date <= horizon.date(),
            ),
            VaccinationSchedule,
        )
    )
    for item in schedules:
        due = datetime.combine(item.due_date, time.min, tzinfo=timezone.utc)
        overdue = item.due_date < now.date()
        items.append(
            HealthReminderResponse(
                kind=(
                    "VACCINATION_OVERDUE"
                    if overdue
                    else "VACCINATION_UPCOMING"
                ),
                source_id=item.id,
                cattle_id=item.cattle_id,
                due_at=due,
                title=f"Vaccination due: {item.vaccine_name}",
                overdue=overdue,
            )
        )

    visits = db.scalars(
        scoped(
            select(VeterinaryVisit).where(
                VeterinaryVisit.status.in_(
                    [
                        VeterinaryVisitStatus.REQUESTED,
                        VeterinaryVisitStatus.SCHEDULED,
                    ]
                ),
                VeterinaryVisit.planned_at.is_not(None),
                VeterinaryVisit.planned_at <= horizon,
            ),
            VeterinaryVisit,
        )
    )
    for item in visits:
        items.append(
            HealthReminderResponse(
                kind="VETERINARY_VISIT",
                source_id=item.id,
                cattle_id=item.cattle_id,
                due_at=item.planned_at,
                title="Veterinary visit scheduled",
                overdue=item.planned_at < now,
            )
        )

    encounter_followups = db.scalars(
        scoped(
            select(HealthEncounter).where(
                HealthEncounter.follow_up_due_at.is_not(None),
                HealthEncounter.follow_up_due_at < now,
            ),
            HealthEncounter,
        )
    )
    vaccination_followups = db.scalars(
        scoped(
            select(VaccinationAdministration).where(
                VaccinationAdministration.follow_up_due_at.is_not(None),
                VaccinationAdministration.follow_up_due_at < now,
            ),
            VaccinationAdministration,
        )
    )
    completed_visit_followups = db.scalars(
        scoped(
            select(VeterinaryVisit).where(
                VeterinaryVisit.status == VeterinaryVisitStatus.COMPLETED,
                VeterinaryVisit.follow_up_due_at.is_not(None),
                VeterinaryVisit.follow_up_due_at < now,
            ),
            VeterinaryVisit,
        )
    )
    for source in [
        *encounter_followups,
        *vaccination_followups,
        *completed_visit_followups,
    ]:
        items.append(
            HealthReminderResponse(
                kind="FOLLOW_UP_OVERDUE",
                source_id=source.id,
                cattle_id=source.cattle_id,
                due_at=source.follow_up_due_at,
                title="Health follow-up overdue",
                overdue=True,
            )
        )

    treatments = db.scalars(
        scoped(
            select(TreatmentPlan).where(
                TreatmentPlan.status.in_(
                    [TreatmentStatus.PLANNED, TreatmentStatus.ACTIVE]
                ),
                or_(
                    TreatmentPlan.end_date.is_(None),
                    TreatmentPlan.end_date <= horizon.date(),
                ),
            ),
            TreatmentPlan,
        )
    )
    for item in treatments:
        due_date = item.end_date or item.start_date
        due = datetime.combine(due_date, time.min, tzinfo=timezone.utc)
        items.append(
            HealthReminderResponse(
                kind="TREATMENT_OUTSTANDING",
                source_id=item.id,
                cattle_id=item.cattle_id,
                due_at=due,
                title=f"Treatment outstanding: {item.name}",
                overdue=due < now,
            )
        )

    unique = {(item.kind, item.source_id): item for item in items}
    ordered = sorted(unique.values(), key=lambda item: (item.due_at, item.kind))
    return ordered[offset : offset + limit]
