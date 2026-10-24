import logging
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.api.v1.cattle.dependencies import (
    CATTLE_PREFIX,
    animal_or_404,
    cattle_responses,
    constraint_name,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import (
    AnimalSex,
    Cattle,
    CattleLifecycleEvent,
    CattleStatus,
    CattleWeightRecord,
    Species,
)
from app.models.user import User
from app.schemas.cattle import (
    CattleCreate,
    CattleResponse,
    CattleSummaryResponse,
    CattleUpdate,
)
from app.services.cattle import (
    CattleValidationError,
    clean_tag,
    get_breed_for_species,
    validate_category,
    validate_not_future,
    validate_parents,
    validate_profile_dates,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix=CATTLE_PREFIX)


def _filtered_cattle_query(
    *,
    farm_id: UUID,
    search: str | None,
    species: Species | None,
    sex: AnimalSex | None,
    breed_id: UUID | None,
    lifecycle_status: CattleStatus | None,
    registered_from: date | None,
    registered_to: date | None,
):
    if registered_from and registered_to and registered_from > registered_to:
        raise HTTPException(
            status_code=422,
            detail="registered_from cannot be after registered_to",
        )
    statement = select(Cattle).where(Cattle.farm_id == farm_id)
    if search and search.strip():
        term = f"%{search.strip()}%"
        statement = statement.where(
            or_(Cattle.tag_number.ilike(term), Cattle.name.ilike(term))
        )
    if species is not None:
        statement = statement.where(Cattle.species == species)
    if sex is not None:
        statement = statement.where(Cattle.sex == sex)
    if breed_id is not None:
        statement = statement.where(Cattle.breed_id == breed_id)
    if lifecycle_status is not None:
        statement = statement.where(Cattle.status == lifecycle_status)
    if registered_from is not None:
        statement = statement.where(Cattle.registration_date >= registered_from)
    if registered_to is not None:
        statement = statement.where(Cattle.registration_date <= registered_to)
    return statement


@router.post(
    "", response_model=CattleResponse, status_code=status.HTTP_201_CREATED
)
def register_cattle(
    farm_id: UUID,
    data: CattleCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_CREATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        tag_number, normalized_tag = clean_tag(data.tag_number)
        validate_category(data.sex, data.category)
        validate_profile_dates(
            date_of_birth=data.date_of_birth,
            birth_date_estimated=data.birth_date_estimated,
            acquisition_date=data.acquisition_date,
        )
        get_breed_for_species(
            db, breed_id=data.breed_id, species=data.species
        )
        validate_parents(
            db,
            farm_id=farm_id,
            species=data.species,
            mother_id=data.mother_id,
            father_id=data.father_id,
        )
        measured_at = (
            validate_not_future(
                data.initial_weight_measured_at,
                field_name="initial_weight_measured_at",
            )
            if data.initial_weight_measured_at is not None
            else datetime.now(timezone.utc)
        )
        if (
            data.initial_weight_kg is not None
            and data.date_of_birth is not None
            and measured_at.date() < data.date_of_birth
        ):
            raise CattleValidationError(
                "Initial weight cannot predate the date of birth"
            )
    except CattleValidationError as error:
        raise validation_error(error) from None

    now = datetime.now(timezone.utc)
    animal = Cattle(
        farm_id=farm_id,
        tag_number=tag_number,
        normalized_tag=normalized_tag,
        name=data.name,
        species=data.species,
        sex=data.sex,
        category=data.category,
        breed_id=data.breed_id,
        date_of_birth=data.date_of_birth,
        birth_date_estimated=data.birth_date_estimated,
        acquisition_date=data.acquisition_date,
        acquisition_method=data.acquisition_method,
        acquisition_source=data.acquisition_source,
        initial_acquisition_cost=data.initial_acquisition_cost,
        initial_acquisition_currency=data.initial_acquisition_currency,
        color=data.color,
        identification_marks=data.identification_marks,
        mother_id=data.mother_id,
        father_id=data.father_id,
        notes=data.notes,
        created_by_id=current_user.id,
    )
    try:
        db.add(animal)
        db.flush()
        db.add(
            CattleLifecycleEvent(
                cattle_id=animal.id,
                farm_id=farm_id,
                previous_status=None,
                new_status=CattleStatus.ACTIVE,
                effective_at=now,
                reason="Initial registration",
                actor_id=current_user.id,
            )
        )
        if data.initial_weight_kg is not None:
            db.add(
                CattleWeightRecord(
                    cattle_id=animal.id,
                    farm_id=farm_id,
                    weight_kg=data.initial_weight_kg,
                    measured_at=measured_at,
                    measurement_method=data.initial_weight_method,
                    recorded_by_id=current_user.id,
                )
            )
        db.commit()
        db.refresh(animal)
    except IntegrityError as error:
        db.rollback()
        if constraint_name(error) == "uq_cattle_farm_tag":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This tag number already exists in the farm",
            ) from None
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cattle registration conflicts with current farm data",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Cattle registration failed")
        raise HTTPException(
            status_code=500, detail="Could not register cattle"
        ) from None
    return cattle_responses(db, [animal])[0]


@router.get("", response_model=list[CattleResponse])
def list_cattle(
    farm_id: UUID,
    search: str | None = Query(default=None, max_length=100),
    species: Species | None = None,
    sex: AnimalSex | None = None,
    breed_id: UUID | None = None,
    lifecycle_status: CattleStatus | None = Query(default=None, alias="status"),
    registered_from: date | None = None,
    registered_to: date | None = None,
    sort: Literal["recent", "tag", "name"] = "recent",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    statement = _filtered_cattle_query(
        farm_id=farm_id,
        search=search,
        species=species,
        sex=sex,
        breed_id=breed_id,
        lifecycle_status=lifecycle_status,
        registered_from=registered_from,
        registered_to=registered_to,
    )
    ordering = {
        "recent": (Cattle.created_at.desc(), Cattle.id),
        "tag": (Cattle.normalized_tag, Cattle.id),
        "name": (
            func.coalesce(func.lower(Cattle.name), Cattle.normalized_tag),
            Cattle.id,
        ),
    }[sort]
    animals = list(
        db.scalars(
            statement.order_by(*ordering)
            .limit(limit)
            .offset(offset)
        )
    )
    return cattle_responses(db, animals)


@router.get("/summary", response_model=CattleSummaryResponse)
def get_cattle_summary(
    farm_id: UUID,
    search: str | None = Query(default=None, max_length=100),
    species: Species | None = None,
    sex: AnimalSex | None = None,
    breed_id: UUID | None = None,
    lifecycle_status: CattleStatus | None = Query(
        default=None,
        alias="status",
    ),
    registered_from: date | None = None,
    registered_to: date | None = None,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    filtered = _filtered_cattle_query(
        farm_id=farm_id,
        search=search,
        species=species,
        sex=sex,
        breed_id=breed_id,
        lifecycle_status=lifecycle_status,
        registered_from=registered_from,
        registered_to=registered_to,
    ).subquery()
    totals = db.execute(
        select(
            func.count(filtered.c.id),
            func.count().filter(filtered.c.sex == AnimalSex.FEMALE),
            func.count().filter(filtered.c.sex == AnimalSex.MALE),
            func.count(func.distinct(filtered.c.breed_id)),
        )
    ).one()
    status_counts = {status: 0 for status in CattleStatus}
    for cattle_status, count in db.execute(
        select(filtered.c.status, func.count(filtered.c.id)).group_by(
            filtered.c.status
        )
    ):
        status_counts[CattleStatus(cattle_status)] = count
    return CattleSummaryResponse(
        total=totals[0],
        female_count=totals[1],
        male_count=totals[2],
        breed_count=totals[3],
        status_counts=status_counts,
    )


@router.get("/{cattle_id}", response_model=CattleResponse)
def get_cattle_profile(
    farm_id: UUID,
    cattle_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    return cattle_responses(
        db, [animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)]
    )[0]


@router.patch("/{cattle_id}", response_model=CattleResponse)
def update_cattle_profile(
    farm_id: UUID,
    cattle_id: UUID,
    data: CattleUpdate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    db: Session = Depends(get_db),
):
    animal = animal_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, lock=True
    )
    values = data.model_dump(exclude_unset=True)
    try:
        for required_field in (
            "category",
            "birth_date_estimated",
            "acquisition_method",
        ):
            if required_field in values and values[required_field] is None:
                raise CattleValidationError(
                    f"{required_field} cannot be null"
                )
        if "tag_number" in values:
            if data.tag_number is None:
                raise CattleValidationError("Tag number cannot be null")
            prospective_tag, prospective_normalized_tag = clean_tag(
                data.tag_number
            )
        else:
            prospective_tag = animal.tag_number
            prospective_normalized_tag = animal.normalized_tag
        prospective_category = data.category or animal.category
        validate_category(animal.sex, prospective_category)
        prospective_dob = (
            data.date_of_birth
            if "date_of_birth" in values
            else animal.date_of_birth
        )
        prospective_estimated = (
            data.birth_date_estimated
            if "birth_date_estimated" in values
            else animal.birth_date_estimated
        )
        prospective_acquisition = (
            data.acquisition_date
            if "acquisition_date" in values
            else animal.acquisition_date
        )
        validate_profile_dates(
            date_of_birth=prospective_dob,
            birth_date_estimated=bool(prospective_estimated),
            acquisition_date=prospective_acquisition,
        )
        prospective_breed = (
            data.breed_id if "breed_id" in values else animal.breed_id
        )
        get_breed_for_species(
            db, breed_id=prospective_breed, species=animal.species
        )
        prospective_mother = (
            data.mother_id if "mother_id" in values else animal.mother_id
        )
        prospective_father = (
            data.father_id if "father_id" in values else animal.father_id
        )
        validate_parents(
            db,
            farm_id=farm_id,
            species=animal.species,
            mother_id=prospective_mother,
            father_id=prospective_father,
            animal_id=animal.id,
        )
        prospective_cost = (
            data.initial_acquisition_cost
            if "initial_acquisition_cost" in values
            else animal.initial_acquisition_cost
        )
        prospective_currency = (
            data.initial_acquisition_currency
            if "initial_acquisition_currency" in values
            else animal.initial_acquisition_currency
        )
        if (prospective_cost is None) != (prospective_currency is None):
            raise CattleValidationError(
                "Acquisition cost and its ISO currency must be provided together"
            )
    except CattleValidationError as error:
        raise validation_error(error) from None

    animal.tag_number = prospective_tag
    animal.normalized_tag = prospective_normalized_tag
    for field, value in values.items():
        if field != "tag_number":
            setattr(animal, field, value)
    try:
        db.commit()
        db.refresh(animal)
    except IntegrityError as error:
        db.rollback()
        if constraint_name(error) == "uq_cattle_farm_tag":
            raise HTTPException(
                status_code=409,
                detail="This tag number already exists in the farm",
            ) from None
        raise HTTPException(
            status_code=409, detail="Invalid cattle update"
        ) from None
    return cattle_responses(db, [animal])[0]
