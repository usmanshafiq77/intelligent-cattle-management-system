
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.milk.dependencies import (
    MILK_PREFIX,
    commit_or_error,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.milk import MilkingSession, MilkingSessionKind
from app.models.user import User
from app.schemas.milk import (
    BulkMilkingCreate,
    BulkMilkingResponse,
    MilkingSessionCreate,
    MilkingSessionResponse,
)
from app.services.milk import (
    MilkValidationError,
    effective_session,
    scoped_lactation,
    scoped_session,
    validate_session_for_create,
)


router = APIRouter(prefix=f"{MILK_PREFIX}/sessions")


def _build_record(
    farm_id: UUID,
    data: MilkingSessionCreate,
    actor_id: UUID,
) -> MilkingSession:
    return MilkingSession(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        lactation_id=data.lactation_id,
        milking_date=data.milking_date,
        session_kind=data.session_kind,
        session_code=data.session_code,
        recorded_time=data.recorded_time,
        volume_liters=data.volume_liters,
        unit=data.unit,
        operator_id=data.operator_id,
        notes=data.notes,
        recorded_by_id=actor_id,
    )


def _lock_lactation(
    db: Session,
    *,
    farm_id: UUID,
    lactation_id: UUID,
) -> None:
    """
    Lock the lactation row until the current transaction ends.

    This coordinates milking writes with lactation transitions
    that acquire a lock on the same row.
    """
    record = scoped_lactation(
        db,
        farm_id=farm_id,
        lactation_id=lactation_id,
        lock=True,
    )

    if record is None:
        raise MilkValidationError("Lactation not found")


@router.post(
    "",
    response_model=MilkingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    farm_id: UUID,
    data: MilkingSessionCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_RECORD)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # Lock the lactation before validating its date boundaries.
        # A concurrent transition must wait for this transaction.
        _lock_lactation(
            db,
            farm_id=farm_id,
            lactation_id=data.lactation_id,
        )

        validate_session_for_create(
            db,
            farm_id=farm_id,
            cattle_id=data.cattle_id,
            lactation_id=data.lactation_id,
            milking_date=data.milking_date,
            operator_id=data.operator_id,
        )

    except MilkValidationError as error:
        db.rollback()
        raise validation_error(error) from None

    record = _build_record(
        farm_id,
        data,
        current_user.id,
    )

    db.add(record)

    commit_or_error(
        db,
        conflict_detail=(
            "A milking record already exists for this "
            "animal, date, and session"
        ),
        server_detail="Could not create milking session",
    )

    db.refresh(record)

    return effective_session(db, record)


@router.post(
    "/bulk",
    response_model=BulkMilkingResponse,
    status_code=status.HTTP_201_CREATED,
)
def bulk_create_sessions(
    farm_id: UUID,
    data: BulkMilkingCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_BULK_CREATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Detect duplicate session identities within the request.
    identities = [
        (
            item.cattle_id,
            item.milking_date,
            item.session_code,
        )
        for item in data.records
    ]

    if len(identities) != len(set(identities)):
        raise HTTPException(
            status_code=409,
            detail="Batch contains duplicate milking identities",
        )

    records: list[MilkingSession] = []

    try:
        # Lock all distinct lactations in a deterministic order.
        # Sorting helps avoid deadlocks between concurrent bulk requests.
        lactation_ids = sorted(
            {item.lactation_id for item in data.records},
            key=str,
        )

        for lactation_id in lactation_ids:
            _lock_lactation(
                db,
                farm_id=farm_id,
                lactation_id=lactation_id,
            )

        # Validate every record before inserting any records.
        for item in data.records:
            validate_session_for_create(
                db,
                farm_id=farm_id,
                cattle_id=item.cattle_id,
                lactation_id=item.lactation_id,
                milking_date=item.milking_date,
                operator_id=item.operator_id,
            )

        # Add all records to the same database transaction.
        for item in data.records:
            record = _build_record(
                farm_id,
                item,
                current_user.id,
            )
            db.add(record)
            records.append(record)

    except MilkValidationError as error:
        db.rollback()
        raise validation_error(error) from None

    # A single commit ensures that database conflicts roll
    # back the whole batch rather than creating partial data.
    commit_or_error(
        db,
        conflict_detail=(
            "Batch conflicts with existing milking data; "
            "no records were created"
        ),
        server_detail="Could not create milking batch",
    )

    return {
        "created": len(records),
        "records": [
            effective_session(db, record)
            for record in records
        ],
    }


@router.get(
    "",
    response_model=list[MilkingSessionResponse],
)
def list_sessions(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    lactation_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    session_kind: MilkingSessionKind | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise HTTPException(
            status_code=422,
            detail="date_from cannot be after date_to",
        )

    query = select(MilkingSession).where(
        MilkingSession.farm_id == farm_id
    )

    if cattle_id is not None:
        query = query.where(
            MilkingSession.cattle_id == cattle_id
        )

    if lactation_id is not None:
        query = query.where(
            MilkingSession.lactation_id == lactation_id
        )

    if date_from is not None:
        query = query.where(
            MilkingSession.milking_date >= date_from
        )

    if date_to is not None:
        query = query.where(
            MilkingSession.milking_date <= date_to
        )

    if session_kind is not None:
        query = query.where(
            MilkingSession.session_kind == session_kind
        )

    records = db.scalars(
        query.order_by(
            MilkingSession.milking_date.desc(),
            MilkingSession.session_code,
            MilkingSession.id,
        )
        .limit(limit)
        .offset(offset)
    )

    return [
        effective_session(db, record)
        for record in records
    ]


@router.get(
    "/{session_id}",
    response_model=MilkingSessionResponse,
)
def get_session(
    farm_id: UUID,
    session_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.MILK_VIEW)
    ),
    db: Session = Depends(get_db),
):
    record = scoped_session(
        db,
        farm_id=farm_id,
        session_id=session_id,
    )

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Milking session not found",
        )

    return effective_session(db, record)
