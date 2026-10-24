import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.cattle.dependencies import (
    CATTLE_PREFIX,
    animal_or_404,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import CattleLifecycleEvent
from app.models.user import User
from app.schemas.cattle import (
    LifecycleEventResponse,
    LifecycleTransitionCreate,
)
from app.services.cattle import (
    CattleValidationError,
    latest_lifecycle_event,
    validate_not_future,
    validate_operational_lifecycle_time,
    validate_transition,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix=CATTLE_PREFIX)


@router.post(
    "/{cattle_id}/lifecycle", response_model=LifecycleEventResponse
)
def transition_cattle_lifecycle(
    farm_id: UUID,
    cattle_id: UUID,
    data: LifecycleTransitionCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    animal = animal_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, lock=True
    )
    try:
        effective_at = validate_not_future(
            data.effective_at, field_name="effective_at"
        )
        validate_transition(animal.status, data.new_status)
        if effective_at < animal.created_at:
            raise CattleValidationError(
                "Lifecycle event cannot predate cattle registration"
            )
        validate_operational_lifecycle_time(
            effective_at=effective_at,
            latest_event=latest_lifecycle_event(
                db,
                farm_id=farm_id,
                cattle_id=cattle_id,
            ),
        )
    except CattleValidationError as error:
        raise validation_error(error) from None
    event = CattleLifecycleEvent(
        cattle_id=animal.id,
        farm_id=farm_id,
        previous_status=animal.status,
        new_status=data.new_status,
        effective_at=effective_at,
        reason=data.reason,
        actor_id=current_user.id,
    )
    animal.status = data.new_status
    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Cattle lifecycle transition failed")
        raise HTTPException(
            status_code=500, detail="Could not change cattle status"
        ) from None
    return event


@router.get(
    "/{cattle_id}/lifecycle", response_model=list[LifecycleEventResponse]
)
def list_cattle_lifecycle(
    farm_id: UUID,
    cattle_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    return db.scalars(
        select(CattleLifecycleEvent)
        .where(
            CattleLifecycleEvent.farm_id == farm_id,
            CattleLifecycleEvent.cattle_id == cattle_id,
        )
        .order_by(
            CattleLifecycleEvent.effective_at.desc(),
            CattleLifecycleEvent.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()
