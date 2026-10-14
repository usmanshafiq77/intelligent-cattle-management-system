import logging
import uuid
from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.core.config import get_settings
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import (
    AnimalSex,
    Breed,
    Cattle,
    CattleLifecycleEvent,
    CattleMedia,
    CattleStatus,
    CattleWeightRecord,
    MediaPurpose,
    Species,
)
from app.models.user import User
from app.schemas.cattle import (
    BreedCreate,
    BreedResponse,
    CattleCreate,
    CattleResponse,
    CattleUpdate,
    LifecycleEventResponse,
    LifecycleTransitionCreate,
    MediaResponse,
    WeightCreate,
    WeightResponse,
)
from app.services.cattle import (
    CattleValidationError,
    clean_tag,
    get_breed_for_species,
    get_cattle_in_farm,
    normalize_identity,
    validate_category,
    validate_not_future,
    validate_parents,
    validate_profile_dates,
    validate_transition,
)
from app.services.media_storage import (
    ALLOWED_IMAGE_TYPES,
    MediaStorage,
    detect_image_content_type,
    get_media_storage,
    validate_original_filename,
)


logger = logging.getLogger(__name__)

breed_router = APIRouter(prefix="/breeds", tags=["Cattle Breeds"])
cattle_router = APIRouter(
    prefix="/farms/{farm_id}/cattle", tags=["Cattle Management"]
)


def _validation_error(error: CattleValidationError | ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def _weight_response(record: CattleWeightRecord) -> WeightResponse:
    return WeightResponse.model_validate(record)


def _cattle_responses(
    db: Session, animals: list[Cattle]
) -> list[CattleResponse]:
    if not animals:
        return []
    cattle_ids = [animal.id for animal in animals]
    breed_ids = {animal.breed_id for animal in animals if animal.breed_id}
    breeds = {
        breed.id: breed
        for breed in db.scalars(
            select(Breed).where(Breed.id.in_(breed_ids))
        )
    }
    ranked_weights = (
        select(
            CattleWeightRecord.id.label("weight_id"),
            func.row_number()
            .over(
                partition_by=CattleWeightRecord.cattle_id,
                order_by=(
                    CattleWeightRecord.measured_at.desc(),
                    CattleWeightRecord.id.desc(),
                ),
            )
            .label("position"),
        )
        .where(CattleWeightRecord.cattle_id.in_(cattle_ids))
        .subquery()
    )
    latest_weights = {
        record.cattle_id: record
        for record in db.scalars(
            select(CattleWeightRecord)
            .join(
                ranked_weights,
                ranked_weights.c.weight_id == CattleWeightRecord.id,
            )
            .where(ranked_weights.c.position == 1)
        )
    }
    media_counts = dict(
        db.execute(
            select(CattleMedia.cattle_id, func.count(CattleMedia.id))
            .where(
                CattleMedia.cattle_id.in_(cattle_ids),
                CattleMedia.removed_at.is_(None),
            )
            .group_by(CattleMedia.cattle_id)
        ).all()
    )
    responses = []
    for animal in animals:
        breed = breeds.get(animal.breed_id)
        latest_weight = latest_weights.get(animal.id)
        responses.append(
            CattleResponse(
                id=animal.id,
                farm_id=animal.farm_id,
                tag_number=animal.tag_number,
                name=animal.name,
                species=animal.species,
                sex=animal.sex,
                category=animal.category,
                breed=(BreedResponse.model_validate(breed) if breed else None),
                date_of_birth=animal.date_of_birth,
                birth_date_estimated=animal.birth_date_estimated,
                registration_date=animal.registration_date,
                acquisition_date=animal.acquisition_date,
                acquisition_method=animal.acquisition_method,
                acquisition_source=animal.acquisition_source,
                initial_acquisition_cost=animal.initial_acquisition_cost,
                initial_acquisition_currency=animal.initial_acquisition_currency,
                color=animal.color,
                identification_marks=animal.identification_marks,
                status=animal.status,
                mother_id=animal.mother_id,
                father_id=animal.father_id,
                notes=animal.notes,
                created_by_id=animal.created_by_id,
                created_at=animal.created_at,
                updated_at=animal.updated_at,
                latest_weight=(
                    _weight_response(latest_weight) if latest_weight else None
                ),
                media_count=media_counts.get(animal.id, 0),
            )
        )
    return responses


def _animal_or_404(
    db: Session, *, farm_id: UUID, cattle_id: UUID, lock: bool = False
) -> Cattle:
    animal = get_cattle_in_farm(
        db, farm_id=farm_id, cattle_id=cattle_id, lock=lock
    )
    if animal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cattle not found",
        )
    return animal


@breed_router.get("", response_model=list[BreedResponse])
def list_breeds(
    species: Species | None = None,
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(Breed).where(Breed.is_active.is_(True))
    if species is not None:
        statement = statement.where(Breed.species == species)
    if search:
        statement = statement.where(Breed.name.ilike(f"%{search.strip()}%"))
    return db.scalars(
        statement.order_by(Breed.species, func.lower(Breed.name), Breed.id)
        .limit(limit)
        .offset(offset)
    ).all()


@breed_router.get("/{breed_id}", response_model=BreedResponse)
def get_breed(
    breed_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    breed = db.scalar(
        select(Breed).where(Breed.id == breed_id, Breed.is_active.is_(True))
    )
    if breed is None:
        raise HTTPException(status_code=404, detail="Breed not found")
    return breed


@breed_router.post(
    "", response_model=BreedResponse, status_code=status.HTTP_201_CREATED
)
def create_breed(
    data: BreedCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a system administrator may manage the global breed catalog",
        )
    breed = Breed(
        species=data.species,
        name=data.name,
        normalized_name=normalize_identity(data.name),
        description=data.description,
        created_by_id=current_user.id,
    )
    try:
        db.add(breed)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This breed already exists for the selected species",
        ) from None
    db.refresh(breed)
    return breed


@cattle_router.post(
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
        raise _validation_error(error) from None

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
        if _constraint_name(error) == "uq_cattle_farm_tag":
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
        raise HTTPException(status_code=500, detail="Could not register cattle") from None
    return _cattle_responses(db, [animal])[0]


@cattle_router.get("", response_model=list[CattleResponse])
def list_cattle(
    farm_id: UUID,
    search: str | None = Query(default=None, max_length=100),
    species: Species | None = None,
    sex: AnimalSex | None = None,
    breed_id: UUID | None = None,
    lifecycle_status: CattleStatus | None = Query(default=None, alias="status"),
    registered_from: date | None = None,
    registered_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if registered_from and registered_to and registered_from > registered_to:
        raise HTTPException(
            status_code=422,
            detail="registered_from cannot be after registered_to",
        )
    statement = select(Cattle).where(Cattle.farm_id == farm_id)
    if search:
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
    animals = list(
        db.scalars(
            statement.order_by(Cattle.created_at.desc(), Cattle.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return _cattle_responses(db, animals)


@cattle_router.get("/{cattle_id}", response_model=CattleResponse)
def get_cattle_profile(
    farm_id: UUID,
    cattle_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    return _cattle_responses(
        db, [_animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)]
    )[0]


@cattle_router.patch("/{cattle_id}", response_model=CattleResponse)
def update_cattle_profile(
    farm_id: UUID,
    cattle_id: UUID,
    data: CattleUpdate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    db: Session = Depends(get_db),
):
    animal = _animal_or_404(
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
        raise _validation_error(error) from None

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
        if _constraint_name(error) == "uq_cattle_farm_tag":
            raise HTTPException(
                status_code=409,
                detail="This tag number already exists in the farm",
            ) from None
        raise HTTPException(status_code=409, detail="Invalid cattle update") from None
    return _cattle_responses(db, [animal])[0]


@cattle_router.post(
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
    animal = _animal_or_404(
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
    except CattleValidationError as error:
        raise _validation_error(error) from None
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
        raise HTTPException(status_code=500, detail="Could not change cattle status") from None
    return event


@cattle_router.get(
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
    _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
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


@cattle_router.post(
    "/{cattle_id}/weights",
    response_model=WeightResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_cattle_weight(
    farm_id: UUID,
    cattle_id: UUID,
    data: WeightCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    animal = _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    try:
        measured_at = validate_not_future(
            data.measured_at, field_name="measured_at"
        )
        if animal.date_of_birth and measured_at.date() < animal.date_of_birth:
            raise CattleValidationError(
                "Weight measurement cannot predate the date of birth"
            )
    except CattleValidationError as error:
        raise _validation_error(error) from None
    record = CattleWeightRecord(
        cattle_id=cattle_id,
        farm_id=farm_id,
        weight_kg=data.weight_kg,
        measured_at=measured_at,
        measurement_method=data.measurement_method,
        recorded_by_id=current_user.id,
        notes=data.notes,
    )
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="A weight already exists at this exact measurement time",
        ) from None
    return record


@cattle_router.get(
    "/{cattle_id}/weights", response_model=list[WeightResponse]
)
def list_cattle_weights(
    farm_id: UUID,
    cattle_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    return db.scalars(
        select(CattleWeightRecord)
        .where(
            CattleWeightRecord.farm_id == farm_id,
            CattleWeightRecord.cattle_id == cattle_id,
        )
        .order_by(
            CattleWeightRecord.measured_at.desc(),
            CattleWeightRecord.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    ).all()


def _media_or_404(
    db: Session, *, farm_id: UUID, cattle_id: UUID, media_id: UUID
) -> CattleMedia:
    media = db.scalar(
        select(CattleMedia).where(
            CattleMedia.id == media_id,
            CattleMedia.farm_id == farm_id,
            CattleMedia.cattle_id == cattle_id,
            CattleMedia.removed_at.is_(None),
        )
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Cattle media not found")
    return media


async def _read_limited_body(request: Request, maximum: int) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > maximum:
            raise HTTPException(status_code=413, detail="Image is too large")
        content.extend(chunk)
    return bytes(content)


@cattle_router.post(
    "/{cattle_id}/media",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    request: Request,
    filename: str = Query(min_length=1, max_length=255),
    purpose: MediaPurpose = MediaPurpose.PROFILE,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
):
    _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    maximum = get_settings().CATTLE_MEDIA_MAX_BYTES
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
            if declared_length < 0:
                raise ValueError
            if declared_length > maximum:
                raise HTTPException(status_code=413, detail="Image is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from None
    content = await _read_limited_body(request, maximum)
    if not content:
        raise HTTPException(status_code=422, detail="Image content is required")
    try:
        original_filename = validate_original_filename(filename)
        detected_type = detect_image_content_type(content)
    except ValueError as error:
        raise _validation_error(error) from None
    declared_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if declared_type not in {detected_type, "application/octet-stream"}:
        raise HTTPException(
            status_code=422,
            detail="Declared content type does not match image content",
        )

    media_id = uuid.uuid4()
    extension = ALLOWED_IMAGE_TYPES[detected_type]
    storage_key = f"cattle/{farm_id}/{cattle_id}/{media_id}{extension}"
    media = CattleMedia(
        id=media_id,
        cattle_id=cattle_id,
        farm_id=farm_id,
        storage_key=storage_key,
        original_filename=original_filename,
        content_type=detected_type,
        size_bytes=len(content),
        purpose=purpose,
        uploaded_by_id=current_user.id,
    )
    try:
        storage.save(storage_key, content)
        db.add(media)
        db.commit()
        db.refresh(media)
    except Exception:
        db.rollback()
        storage.delete(storage_key)
        logger.exception("Cattle media upload failed")
        raise HTTPException(status_code=500, detail="Could not store cattle media") from None
    return media


@cattle_router.get(
    "/{cattle_id}/media", response_model=list[MediaResponse]
)
def list_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    return db.scalars(
        select(CattleMedia)
        .where(
            CattleMedia.farm_id == farm_id,
            CattleMedia.cattle_id == cattle_id,
            CattleMedia.removed_at.is_(None),
        )
        .order_by(CattleMedia.uploaded_at.desc(), CattleMedia.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()


@cattle_router.get(
    "/{cattle_id}/media/{media_id}", response_model=MediaResponse
)
def get_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    media_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    return _media_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, media_id=media_id
    )


@cattle_router.get("/{cattle_id}/media/{media_id}/content")
def get_cattle_media_content(
    farm_id: UUID,
    cattle_id: UUID,
    media_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_VIEW)
    ),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
):
    _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    media = _media_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, media_id=media_id
    )
    try:
        path = storage.resolve(media.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Media content not found") from None
    return FileResponse(
        path=path,
        media_type=media.content_type,
        filename=media.original_filename,
    )


@cattle_router.delete(
    "/{cattle_id}/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_cattle_media(
    farm_id: UUID,
    cattle_id: UUID,
    media_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.CATTLE_UPDATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: MediaStorage = Depends(get_media_storage),
):
    _animal_or_404(db, farm_id=farm_id, cattle_id=cattle_id)
    media = _media_or_404(
        db, farm_id=farm_id, cattle_id=cattle_id, media_id=media_id
    )
    media.removed_at = datetime.now(timezone.utc)
    media.removed_by_id = current_user.id
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Cattle media removal failed")
        raise HTTPException(status_code=500, detail="Could not remove cattle media") from None
    try:
        storage.delete(media.storage_key)
    except OSError:
        logger.exception("Removed cattle media file cleanup failed")
    return None
