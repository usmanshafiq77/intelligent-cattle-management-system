import unicodedata
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cattle import (
    AnimalCategory,
    AnimalSex,
    Breed,
    Cattle,
    CattleStatus,
    Species,
)


class CattleValidationError(ValueError):
    pass


VALID_TRANSITIONS: dict[CattleStatus, frozenset[CattleStatus]] = {
    CattleStatus.ACTIVE: frozenset(
        {
            CattleStatus.SOLD,
            CattleStatus.DECEASED,
            CattleStatus.TRANSFERRED,
            CattleStatus.MISSING,
            CattleStatus.ARCHIVED,
        }
    ),
    CattleStatus.MISSING: frozenset(
        {CattleStatus.ACTIVE, CattleStatus.DECEASED}
    ),
    CattleStatus.SOLD: frozenset(),
    CattleStatus.DECEASED: frozenset(),
    CattleStatus.TRANSFERRED: frozenset(),
    CattleStatus.ARCHIVED: frozenset(),
}


def normalize_identity(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def clean_tag(value: str) -> tuple[str, str]:
    display = " ".join(unicodedata.normalize("NFKC", value).split())
    if not display or len(display) > 100:
        raise CattleValidationError("Tag number must contain 1 to 100 characters")
    return display, display.casefold()


def validate_category(sex: AnimalSex, category: AnimalCategory) -> None:
    if category in {AnimalCategory.HEIFER, AnimalCategory.COW} and sex != AnimalSex.FEMALE:
        raise CattleValidationError("Heifer and cow categories require FEMALE sex")
    if category in {AnimalCategory.BULL, AnimalCategory.STEER} and sex != AnimalSex.MALE:
        raise CattleValidationError("Bull and steer categories require MALE sex")


def validate_profile_dates(
    *,
    date_of_birth: date | None,
    birth_date_estimated: bool,
    acquisition_date: date | None,
) -> None:
    today = date.today()
    if date_of_birth is not None and date_of_birth > today:
        raise CattleValidationError("Date of birth cannot be in the future")
    if birth_date_estimated and date_of_birth is None:
        raise CattleValidationError(
            "An estimated birth date requires date_of_birth"
        )
    if acquisition_date is not None and acquisition_date > today:
        raise CattleValidationError("Acquisition date cannot be in the future")
    if (
        date_of_birth is not None
        and acquisition_date is not None
        and acquisition_date < date_of_birth
    ):
        raise CattleValidationError(
            "Acquisition date cannot precede the date of birth"
        )


def validate_not_future(moment: datetime, *, field_name: str) -> datetime:
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise CattleValidationError(f"{field_name} must include a timezone")
    normalized = moment.astimezone(timezone.utc)
    if normalized > datetime.now(timezone.utc):
        raise CattleValidationError(f"{field_name} cannot be in the future")
    return normalized


def get_breed_for_species(
    db: Session, *, breed_id: UUID | None, species: Species
) -> Breed | None:
    if breed_id is None:
        return None
    breed = db.scalar(
        select(Breed).where(Breed.id == breed_id, Breed.is_active.is_(True))
    )
    if breed is None:
        raise CattleValidationError("Breed not found")
    if breed.species != species:
        raise CattleValidationError("Breed does not match the animal species")
    return breed


def get_cattle_in_farm(
    db: Session,
    *,
    farm_id: UUID,
    cattle_id: UUID,
    lock: bool = False,
) -> Cattle | None:
    statement = select(Cattle).where(
        Cattle.id == cattle_id, Cattle.farm_id == farm_id
    )
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def _parent(
    db: Session,
    *,
    farm_id: UUID,
    parent_id: UUID | None,
    expected_sex: AnimalSex,
    species: Species,
    label: str,
) -> Cattle | None:
    if parent_id is None:
        return None
    parent = get_cattle_in_farm(
        db, farm_id=farm_id, cattle_id=parent_id
    )
    if parent is None:
        raise CattleValidationError(f"{label} was not found in this farm")
    if parent.sex != expected_sex:
        raise CattleValidationError(f"{label} has an invalid sex")
    if parent.species != species:
        raise CattleValidationError(f"{label} has a different species")
    return parent


def _assert_no_ancestry_cycle(
    db: Session, *, animal_id: UUID, proposed_parent: Cattle | None
) -> None:
    if proposed_parent is None:
        return
    pending = [proposed_parent]
    visited: set[UUID] = set()
    while pending:
        candidate = pending.pop()
        if candidate.id == animal_id:
            raise CattleValidationError("Parent assignment would create a cycle")
        if candidate.id in visited:
            continue
        visited.add(candidate.id)
        parent_ids = {
            parent_id
            for parent_id in (candidate.mother_id, candidate.father_id)
            if parent_id is not None
        }
        if parent_ids:
            pending.extend(
                db.scalars(
                    select(Cattle).where(Cattle.id.in_(parent_ids))
                ).all()
            )


def validate_parents(
    db: Session,
    *,
    farm_id: UUID,
    species: Species,
    mother_id: UUID | None,
    father_id: UUID | None,
    animal_id: UUID | None = None,
) -> None:
    if mother_id is not None and mother_id == father_id:
        raise CattleValidationError("Mother and father must be different animals")
    if animal_id is not None and animal_id in {mother_id, father_id}:
        raise CattleValidationError("An animal cannot be its own parent")
    mother = _parent(
        db,
        farm_id=farm_id,
        parent_id=mother_id,
        expected_sex=AnimalSex.FEMALE,
        species=species,
        label="Mother",
    )
    father = _parent(
        db,
        farm_id=farm_id,
        parent_id=father_id,
        expected_sex=AnimalSex.MALE,
        species=species,
        label="Father",
    )
    if animal_id is not None:
        _assert_no_ancestry_cycle(db, animal_id=animal_id, proposed_parent=mother)
        _assert_no_ancestry_cycle(db, animal_id=animal_id, proposed_parent=father)


def validate_transition(
    current: CattleStatus, requested: CattleStatus
) -> None:
    if requested not in VALID_TRANSITIONS[current]:
        raise CattleValidationError(
            f"Invalid lifecycle transition: {current.value} to {requested.value}"
        )
