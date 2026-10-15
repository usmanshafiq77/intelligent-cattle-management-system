from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.health.dependencies import (
    HEALTH_PREFIX,
    commit_or_error,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.health import VeterinaryVisit, VeterinaryVisitStatus
from app.models.user import User
from app.schemas.health import (
    VeterinaryVisitCreate,
    VeterinaryVisitResponse,
    VeterinaryVisitUpdate,
)
from app.services.health import (
    HealthValidationError,
    add_audit_event,
    cattle_for_health_action,
    scoped_record,
    serializable_snapshot,
    validate_active_member,
    validate_visit_transition,
)


router = APIRouter(prefix=HEALTH_PREFIX)


@router.post(
    "/veterinary-visits",
    response_model=VeterinaryVisitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_veterinary_visit(
    farm_id: UUID,
    data: VeterinaryVisitCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VISIT_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    try:
        cattle_for_health_action(
            db, farm_id=farm_id, cattle_id=data.cattle_id
        )
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.veterinarian_user_id,
            field_name="veterinarian_user_id",
        )
        if data.planned_at and data.planned_at < now:
            raise HealthValidationError("planned_at cannot be in the past")
    except HealthValidationError as error:
        raise validation_error(error) from None
    visit = VeterinaryVisit(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        status=(
            VeterinaryVisitStatus.SCHEDULED
            if data.planned_at
            else VeterinaryVisitStatus.REQUESTED
        ),
        requested_at=now,
        planned_at=data.planned_at,
        veterinarian_user_id=data.veterinarian_user_id,
        reason=data.reason,
        created_by_id=current_user.id,
    )
    db.add(visit)
    commit_or_error(
        db,
        conflict_detail="Veterinary visit conflicts with existing data",
        server_detail="Could not create veterinary visit",
    )
    db.refresh(visit)
    return visit


@router.get(
    "/veterinary-visits", response_model=list[VeterinaryVisitResponse]
)
def list_veterinary_visits(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    visit_status: VeterinaryVisitStatus | None = Query(
        default=None, alias="status"
    ),
    planned_from: datetime | None = None,
    planned_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if planned_from and planned_to and planned_from > planned_to:
        raise HTTPException(status_code=422, detail="Invalid planned date range")
    statement = select(VeterinaryVisit).where(
        VeterinaryVisit.farm_id == farm_id
    )
    if cattle_id:
        statement = statement.where(VeterinaryVisit.cattle_id == cattle_id)
    if visit_status:
        statement = statement.where(VeterinaryVisit.status == visit_status)
    if planned_from:
        statement = statement.where(VeterinaryVisit.planned_at >= planned_from)
    if planned_to:
        statement = statement.where(VeterinaryVisit.planned_at <= planned_to)
    return list(
        db.scalars(
            statement.order_by(
                VeterinaryVisit.planned_at.asc().nulls_last(),
                VeterinaryVisit.requested_at.desc(),
                VeterinaryVisit.id,
            )
            .limit(limit)
            .offset(offset)
        )
    )


@router.patch(
    "/veterinary-visits/{visit_id}",
    response_model=VeterinaryVisitResponse,
)
def update_veterinary_visit(
    farm_id: UUID,
    visit_id: UUID,
    data: VeterinaryVisitUpdate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VISIT_MANAGE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    visit = scoped_record(
        db,
        VeterinaryVisit,
        farm_id=farm_id,
        record_id=visit_id,
        lock=True,
    )
    if visit is None:
        raise HTTPException(status_code=404, detail="Veterinary visit not found")
    now = datetime.now(timezone.utc)
    try:
        validate_visit_transition(visit.status, data.status)
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.veterinarian_user_id,
            field_name="veterinarian_user_id",
        )
        if data.status == VeterinaryVisitStatus.SCHEDULED:
            if data.planned_at is None:
                raise HealthValidationError(
                    "planned_at is required when scheduling a visit"
                )
            if data.planned_at < visit.requested_at:
                raise HealthValidationError(
                    "planned_at cannot predate the visit request"
                )
        if data.status == VeterinaryVisitStatus.COMPLETED:
            if data.actual_at is None:
                raise HealthValidationError(
                    "actual_at is required when completing a visit"
                )
            if data.actual_at > now:
                raise HealthValidationError("actual_at cannot be in the future")
            if data.actual_at < visit.requested_at:
                raise HealthValidationError(
                    "actual_at cannot predate the visit request"
                )
            if (
                data.follow_up_due_at
                and data.follow_up_due_at < data.actual_at
            ):
                raise HealthValidationError(
                    "follow_up_due_at cannot predate actual_at"
                )
    except HealthValidationError as error:
        raise validation_error(error) from None
    previous = serializable_snapshot(visit)
    if data.planned_at is not None:
        visit.planned_at = data.planned_at
    if data.veterinarian_user_id is not None:
        visit.veterinarian_user_id = data.veterinarian_user_id
    visit.status = data.status
    if data.status == VeterinaryVisitStatus.COMPLETED:
        visit.actual_at = data.actual_at
        visit.clinical_notes = data.clinical_notes
        visit.follow_up_due_at = data.follow_up_due_at
        visit.follow_up_notes = data.follow_up_notes
    elif data.status == VeterinaryVisitStatus.CANCELLED:
        visit.cancellation_reason = data.reason
    add_audit_event(
        db,
        farm_id=farm_id,
        cattle_id=visit.cattle_id,
        record_type="VETERINARY_VISIT",
        record_id=visit.id,
        action=f"STATUS_{data.status.value}",
        reason=data.reason,
        actor_id=current_user.id,
        previous_data=previous,
    )
    commit_or_error(
        db,
        conflict_detail="Veterinary visit changed concurrently",
        server_detail="Could not update veterinary visit",
    )
    db.refresh(visit)
    return visit
