from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.breeding import (BreedingAuditAction, BreedingAuditEvent, BreedingEvent, BreedingEventStatus, BreedingMethod, BreedingReminder, CalvingEvent, CalvingOffspring, HeatObservation, ParentRole, ParentageVerification, PregnancyAssessment, PregnancyExamination, PregnancyLoss, ReminderStatus, ReminderType)
from app.models.cattle import AcquisitionMethod, AnimalCategory, AnimalSex, Cattle, CattleStatus, CattleWeightRecord
from app.models.farm_member import FarmMember, MemberStatus
from app.schemas.breeding import OffspringCreate, ParentageCreate, PedigreeNode
from app.services.cattle import CattleValidationError, clean_tag, get_breed_for_species, get_cattle_in_farm, validate_category, validate_parents


DEFAULT_GESTATION_DAYS = 283


class BreedingValidationError(ValueError):
    pass


def aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise BreedingValidationError(f"{field} must include a timezone")
    return value.astimezone(timezone.utc)


def female(db: Session, farm_id: UUID, cattle_id: UUID, *, lock: bool = False) -> Cattle:
    animal = get_cattle_in_farm(db, farm_id=farm_id, cattle_id=cattle_id, lock=lock)
    if animal is None:
        raise BreedingValidationError("Female cattle was not found in this farm")
    if animal.sex != AnimalSex.FEMALE:
        raise BreedingValidationError("This workflow requires a female animal")
    if animal.status != CattleStatus.ACTIVE:
        raise BreedingValidationError("This workflow requires an active animal")
    return animal


def sire(db: Session, farm_id: UUID, cattle_id: UUID | None, species=None) -> Cattle | None:
    if cattle_id is None:
        return None
    animal = get_cattle_in_farm(db, farm_id=farm_id, cattle_id=cattle_id)
    if animal is None:
        raise BreedingValidationError("Sire was not found in this farm")
    if animal.sex != AnimalSex.MALE:
        raise BreedingValidationError("Sire must be male")
    if species is not None and animal.species != species:
        raise BreedingValidationError("Sire and cow species must match")
    return animal


def scoped(db: Session, model, farm_id: UUID, record_id: UUID):
    record = db.scalar(select(model).where(model.id == record_id, model.farm_id == farm_id))
    if record is None:
        raise BreedingValidationError("Record was not found in this farm")
    return record


def member_exists(db: Session, farm_id: UUID, user_id: UUID) -> bool:
    return db.scalar(select(func.count()).select_from(FarmMember).where(FarmMember.farm_id == farm_id, FarmMember.user_id == user_id, FarmMember.status == MemberStatus.ACTIVE)) > 0


def audit(db: Session, *, farm_id: UUID, entity_type: str, entity_id: UUID, action: BreedingAuditAction, summary: str, actor_id: UUID) -> None:
    db.add(BreedingAuditEvent(farm_id=farm_id, entity_type=entity_type, entity_id=entity_id, action=action, summary=summary, actor_id=actor_id))


def estimated_heat(observed_at: datetime, cycle_length_days: int) -> datetime:
    return aware(observed_at, "observed_at") + timedelta(days=cycle_length_days)


def estimated_calving(db: Session, *, farm_id: UUID, cattle_id: UUID, breeding_event_id: UUID | None, examined_at: datetime, gestation_days: int) -> date:
    base = aware(examined_at, "examined_at")
    if breeding_event_id:
        event = scoped(db, BreedingEvent, farm_id, breeding_event_id)
        if event.cow_id != cattle_id or event.status not in {BreedingEventStatus.COMPLETED, BreedingEventStatus.FOLLOW_UP_REQUIRED}:
            raise BreedingValidationError("Breeding event is not an eligible completed event for this animal")
        base = event.completed_at or event.scheduled_at
    return (base + timedelta(days=gestation_days)).date()


def validate_breeding(db: Session, *, farm_id: UUID, cow_id: UUID, sire_id: UUID | None, method: BreedingMethod, scheduled_at: datetime, completed_at: datetime | None) -> None:
    cow = female(db, farm_id, cow_id)
    sire(db, farm_id, sire_id, cow.species)
    scheduled = aware(scheduled_at, "scheduled_at")
    if completed_at:
        completed = aware(completed_at, "completed_at")
        if completed < scheduled:
            raise BreedingValidationError("completed_at cannot precede scheduled_at")
        if completed > datetime.now(timezone.utc):
            raise BreedingValidationError("completed_at cannot be in the future")
    if method == BreedingMethod.NATURAL_MATING and sire_id is None:
        raise BreedingValidationError("Natural mating requires a sire")


def validate_exam(db: Session, *, farm_id: UUID, cattle_id: UUID, breeding_event_id: UUID | None, examined_at: datetime, supersedes_id: UUID | None) -> Cattle:
    animal = female(db, farm_id, cattle_id)
    examined = aware(examined_at, "examined_at")
    if examined > datetime.now(timezone.utc):
        raise BreedingValidationError("examined_at cannot be in the future")
    if breeding_event_id:
        event = scoped(db, BreedingEvent, farm_id, breeding_event_id)
        if event.cow_id != cattle_id or examined < event.scheduled_at:
            raise BreedingValidationError("Examination must follow the selected animal's breeding event")
    if supersedes_id:
        prior = scoped(db, PregnancyExamination, farm_id, supersedes_id)
        if prior.cattle_id != cattle_id or examined <= prior.examined_at:
            raise BreedingValidationError("A correction must follow and refer to an examination for this animal")
    return animal


def validate_calving(db: Session, *, farm_id: UUID, dam_id: UUID, breeding_event_id: UUID | None, calved_at: datetime) -> Cattle:
    animal = female(db, farm_id, dam_id, lock=True)
    calved = aware(calved_at, "calved_at")
    if calved > datetime.now(timezone.utc):
        raise BreedingValidationError("calved_at cannot be in the future")
    if animal.date_of_birth and calved.date() < animal.date_of_birth:
        raise BreedingValidationError("Calving cannot precede the dam's birth")
    if breeding_event_id:
        event = scoped(db, BreedingEvent, farm_id, breeding_event_id)
        if event.cow_id != dam_id or calved < event.scheduled_at:
            raise BreedingValidationError("Calving must follow the selected dam's breeding event")
    return animal


def register_offspring(db: Session, *, farm_id: UUID, event: CalvingEvent, data: OffspringCreate, actor_id: UUID) -> CalvingOffspring:
    dam = female(db, farm_id, event.dam_id, lock=True)
    if data.species != dam.species:
        raise BreedingValidationError("Offspring and dam species must match")
    validate_category(data.sex, data.category)
    get_breed_for_species(db, breed_id=data.breed_id, species=data.species)
    known_sire = data.sire_id
    if known_sire is None and event.breeding_event_id:
        known_sire = scoped(db, BreedingEvent, farm_id, event.breeding_event_id).sire_id
    validate_parents(db, farm_id=farm_id, species=data.species, mother_id=dam.id, father_id=known_sire)
    tag, normalized = clean_tag(data.tag_number)
    if db.scalar(select(Cattle.id).where(Cattle.farm_id == farm_id, Cattle.normalized_tag == normalized)):
        raise BreedingValidationError("An animal with this tag already exists in the farm")
    if db.scalar(select(CalvingOffspring.id).where(CalvingOffspring.calving_event_id == event.id, CalvingOffspring.birth_order == data.birth_order)):
        raise BreedingValidationError("This birth order is already registered for the calving")
    if data.birth_order > event.calf_count:
        raise BreedingValidationError("Birth order cannot exceed the recorded calf count")
    calf = Cattle(farm_id=farm_id, tag_number=tag, normalized_tag=normalized, name=data.name, species=data.species, sex=data.sex, category=data.category, breed_id=data.breed_id, date_of_birth=event.calved_at.date(), acquisition_date=event.calved_at.date(), acquisition_method=AcquisitionMethod.BORN_ON_FARM, mother_id=dam.id, father_id=known_sire, notes=data.notes, created_by_id=actor_id)
    db.add(calf)
    db.flush()
    link = CalvingOffspring(farm_id=farm_id, calving_event_id=event.id, cattle_id=calf.id, birth_order=data.birth_order, birth_weight_kg=data.birth_weight_kg, registered_by_id=actor_id)
    db.add(link)
    if data.birth_weight_kg:
        db.add(CattleWeightRecord(cattle_id=calf.id, farm_id=farm_id, weight_kg=data.birth_weight_kg, measured_at=event.calved_at, measurement_method="BIRTH_WEIGHT", recorded_by_id=actor_id, notes="Recorded during offspring registration"))
    audit(db, farm_id=farm_id, entity_type="calving", entity_id=event.id, action=BreedingAuditAction.OFFSPRING_REGISTERED, summary=f"Registered offspring {tag} at birth order {data.birth_order}", actor_id=actor_id)
    return link


def assign_parentage(db: Session, *, farm_id: UUID, data: ParentageCreate, actor_id: UUID) -> ParentageVerification:
    child = get_cattle_in_farm(db, farm_id=farm_id, cattle_id=data.child_id, lock=True)
    if child is None:
        raise BreedingValidationError("Child was not found in this farm")
    current_parent_id = child.mother_id if data.parent_role == ParentRole.DAM else child.father_id
    if current_parent_id is not None and current_parent_id != data.parent_id:
        raise BreedingValidationError(
            f"Recorded {data.parent_role.value.lower()} already differs; use an explicit audited correction process"
        )
    mother_id = data.parent_id if data.parent_role == ParentRole.DAM else child.mother_id
    father_id = data.parent_id if data.parent_role == ParentRole.SIRE else child.father_id
    try:
        validate_parents(db, farm_id=farm_id, species=child.species, mother_id=mother_id, father_id=father_id, animal_id=child.id)
    except CattleValidationError as exc:
        raise BreedingValidationError(str(exc)) from exc
    setattr(child, "mother_id" if data.parent_role == ParentRole.DAM else "father_id", data.parent_id)
    record = ParentageVerification(farm_id=farm_id, child_id=child.id, parent_id=data.parent_id, parent_role=data.parent_role, status=data.status, confidence_percent=data.confidence_percent, evidence_reference=data.evidence_reference, client_request_id=data.client_request_id, recorded_by_id=actor_id)
    db.add(record)
    audit(db, farm_id=farm_id, entity_type="cattle", entity_id=child.id, action=BreedingAuditAction.PARENTAGE_CHANGED, summary=f"Recorded {data.parent_role.value.lower()} parentage as {data.status.value}", actor_id=actor_id)
    return record


def pedigree(db: Session, *, farm_id: UUID, cattle_id: UUID, generations: int) -> tuple[PedigreeNode, list[PedigreeNode], bool]:
    subject = get_cattle_in_farm(db, farm_id=farm_id, cattle_id=cattle_id)
    if subject is None:
        raise BreedingValidationError("Animal was not found in this farm")
    breed_names = {}
    from app.models.cattle import Breed
    breed_names.update(dict(db.execute(select(Breed.id, Breed.name)).all()))
    def node(animal, generation, relationship):
        verification = db.scalar(select(ParentageVerification).where(ParentageVerification.farm_id == farm_id, ParentageVerification.child_id == (subject.id if generation == 1 else animal.id), ParentageVerification.parent_id == animal.id).order_by(ParentageVerification.created_at.desc()).limit(1)) if generation else None
        return PedigreeNode(cattle_id=animal.id, tag_number=animal.tag_number, name=animal.name, sex=animal.sex, breed_name=breed_names.get(animal.breed_id), generation=generation, relationship=relationship, parentage_status=verification.status if verification else None, confidence_percent=verification.confidence_percent if verification else None)
    root = node(subject, 0, "SELF")
    ancestors, frontier, incomplete, visited = [], [(subject, 0)], False, {subject.id}
    while frontier:
        current, generation = frontier.pop(0)
        if generation >= generations:
            continue
        for parent_id, relation in ((current.mother_id, "DAM"), (current.father_id, "SIRE")):
            if parent_id is None:
                incomplete = True
                continue
            parent = get_cattle_in_farm(db, farm_id=farm_id, cattle_id=parent_id)
            if parent is None or parent.id in visited:
                incomplete = True
                continue
            visited.add(parent.id)
            ancestors.append(node(parent, generation + 1, relation))
            frontier.append((parent, generation + 1))
    return root, ancestors, incomplete


def latest_pregnancy_states(db: Session, farm_id: UUID) -> dict[UUID, PregnancyAssessment]:
    rows = db.execute(select(PregnancyExamination).where(PregnancyExamination.farm_id == farm_id).order_by(PregnancyExamination.cattle_id, PregnancyExamination.examined_at.desc(), PregnancyExamination.created_at.desc())).scalars()
    result = {}
    for row in rows:
        result.setdefault(row.cattle_id, row.assessment)
    return result
