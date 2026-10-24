from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission, require_veterinarian_permission
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.breeding import (BreedingAuditAction, BreedingAuditEvent, BreedingEvent, BreedingEventStatus, BreedingReminder, CalvingEvent, CalvingOffspring, HeatObservation, ParentageVerification, PregnancyAssessment, PregnancyExamination, PregnancyLoss, ReminderStatus)
from app.models.cattle import Cattle
from app.schemas.breeding import (BreedingDashboardResponse, BreedingEventCreate, BreedingEventResponse, BreedingEventUpdate, BreedingReportResponse, CalvingClinicalUpdate, CalvingEventCreate, CalvingEventResponse, HeatObservationCreate, HeatObservationResponse, OffspringCreate, OffspringResponse, ParentageCreate, ParentageResponse, PedigreeResponse, PregnancyExaminationCreate, PregnancyExaminationResponse, PregnancyLossCreate, PregnancyLossResponse, ReminderCreate, ReminderResponse, ReminderUpdate)
from app.services.breeding import (BreedingValidationError, DEFAULT_GESTATION_DAYS, assign_parentage, audit, estimated_calving, estimated_heat, female, latest_pregnancy_states, member_exists, pedigree, register_offspring, scoped, validate_breeding, validate_calving, validate_exam)


router = APIRouter(prefix="/farms/{farm_id}/breeding", tags=["Breeding & Genetics"])


def invalid(exc: Exception, code: int = 422):
    raise HTTPException(status_code=code, detail=str(exc)) from exc


def commit(db: Session, conflict: str):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        invalid(Exception(conflict), 409)


def flush(db: Session, conflict: str):
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        invalid(Exception(conflict), 409)


@router.get("/dashboard", response_model=BreedingDashboardResponse)
def dashboard(farm_id: UUID, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    now, horizon = datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(days=30)
    states = latest_pregnancy_states(db, farm_id)
    return BreedingDashboardResponse(
        heat_observations=db.scalar(select(func.count(HeatObservation.id)).where(HeatObservation.farm_id == farm_id)) or 0,
        planned_breedings=db.scalar(select(func.count(BreedingEvent.id)).where(BreedingEvent.farm_id == farm_id, BreedingEvent.status == BreedingEventStatus.PLANNED)) or 0,
        completed_breedings=db.scalar(select(func.count(BreedingEvent.id)).where(BreedingEvent.farm_id == farm_id, BreedingEvent.status == BreedingEventStatus.COMPLETED)) or 0,
        currently_pregnant=sum(value == PregnancyAssessment.PREGNANT for value in states.values()),
        upcoming_calvings=db.scalar(select(func.count(PregnancyExamination.id)).where(PregnancyExamination.farm_id == farm_id, PregnancyExamination.assessment == PregnancyAssessment.PREGNANT, PregnancyExamination.expected_calving_date.between(now.date(), horizon.date()))) or 0,
        pending_follow_ups=db.scalar(select(func.count(BreedingReminder.id)).where(BreedingReminder.farm_id == farm_id, BreedingReminder.status == ReminderStatus.OPEN, BreedingReminder.due_at <= horizon)) or 0,
        calves_born=db.scalar(select(func.count(CalvingOffspring.id)).where(CalvingOffspring.farm_id == farm_id)) or 0,
    )


@router.get("/heat-observations", response_model=list[HeatObservationResponse])
def list_heat(farm_id: UUID, cattle_id: UUID | None = None, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    statement = select(HeatObservation).where(HeatObservation.farm_id == farm_id)
    if cattle_id: statement = statement.where(HeatObservation.cattle_id == cattle_id)
    return db.scalars(statement.order_by(HeatObservation.observed_at.desc()).limit(500)).all()


@router.post("/heat-observations", response_model=HeatObservationResponse, status_code=201)
def create_heat(farm_id: UUID, data: HeatObservationCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_HEAT_RECORD))):
    try:
        female(db, farm_id, data.cattle_id)
        observed = data.observed_at.astimezone(timezone.utc) if data.observed_at.tzinfo else (_ for _ in ()).throw(BreedingValidationError("observed_at must include a timezone"))
        if observed > datetime.now(timezone.utc): raise BreedingValidationError("observed_at cannot be in the future")
        next_heat = estimated_heat(observed, data.cycle_length_days)
        record = HeatObservation(farm_id=farm_id, cattle_id=data.cattle_id, client_request_id=data.client_request_id, observed_at=observed, signs=data.signs, intensity=data.intensity, notes=data.notes, estimated_next_heat_at=next_heat, cycle_length_days=data.cycle_length_days, observed_by_id=access.membership.user_id)
        db.add(record); flush(db, "This heat observation request has already been recorded")
        audit(db, farm_id=farm_id, entity_type="heat_observation", entity_id=record.id, action=BreedingAuditAction.CREATED, summary="Recorded heat observation with an explicitly estimated next cycle", actor_id=access.membership.user_id)
        if data.create_reminder:
            db.add(BreedingReminder(farm_id=farm_id, cattle_id=data.cattle_id, client_request_id=record.id, reminder_type="ESTIMATED_HEAT", due_at=next_heat, title="Estimated next heat", notes="Cycle-based estimate; observe the animal before action.", is_estimate=True, created_by_id=access.membership.user_id))
        commit(db, "This heat observation request has already been recorded")
        db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc)


@router.get("/events", response_model=list[BreedingEventResponse])
def list_events(farm_id: UUID, cattle_id: UUID | None = None, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    q = select(BreedingEvent).where(BreedingEvent.farm_id == farm_id)
    if cattle_id: q = q.where(BreedingEvent.cow_id == cattle_id)
    return db.scalars(q.order_by(BreedingEvent.scheduled_at.desc()).limit(500)).all()


@router.post("/events", response_model=BreedingEventResponse, status_code=201)
def create_event(farm_id: UUID, data: BreedingEventCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_EVENT_RECORD))):
    try:
        validate_breeding(db, farm_id=farm_id, cow_id=data.cow_id, sire_id=data.sire_id, method=data.method, scheduled_at=data.scheduled_at, completed_at=data.completed_at)
        record = BreedingEvent(farm_id=farm_id, recorded_by_id=access.membership.user_id, **data.model_dump())
        db.add(record); flush(db, "This breeding event request has already been recorded"); audit(db, farm_id=farm_id, entity_type="breeding_event", entity_id=record.id, action=BreedingAuditAction.CREATED, summary=f"Recorded {record.method.value} as {record.status.value}; conception not inferred", actor_id=access.membership.user_id)
        commit(db, "This breeding event request has already been recorded"); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc)


@router.patch("/events/{event_id}", response_model=BreedingEventResponse)
def update_event(farm_id: UUID, event_id: UUID, data: BreedingEventUpdate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_EVENT_RECORD))):
    try:
        record = scoped(db, BreedingEvent, farm_id, event_id)
        if data.status == BreedingEventStatus.COMPLETED and not data.completed_at: raise BreedingValidationError("Completed breeding requires completed_at")
        if data.completed_at and data.completed_at < record.scheduled_at: raise BreedingValidationError("completed_at cannot precede scheduled_at")
        old = record.status
        record.status, record.completed_at, record.follow_up_due_at, record.notes = data.status, data.completed_at, data.follow_up_due_at, data.notes
        audit(db, farm_id=farm_id, entity_type="breeding_event", entity_id=record.id, action=BreedingAuditAction.STATUS_CHANGED, summary=f"Status changed from {old.value} to {record.status.value}", actor_id=access.membership.user_id)
        db.commit(); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc, 404 if "not found" in str(exc) else 422)


@router.get("/pregnancy-examinations", response_model=list[PregnancyExaminationResponse])
def list_exams(farm_id: UUID, cattle_id: UUID | None = None, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    q = select(PregnancyExamination).where(PregnancyExamination.farm_id == farm_id)
    if cattle_id: q = q.where(PregnancyExamination.cattle_id == cattle_id)
    return db.scalars(q.order_by(PregnancyExamination.examined_at.desc()).limit(500)).all()


@router.post("/pregnancy-examinations", response_model=PregnancyExaminationResponse, status_code=201)
def create_exam(farm_id: UUID, data: PregnancyExaminationCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_veterinarian_permission(Permission.BREEDING_PREGNANCY_ASSESS))):
    try:
        validate_exam(db, farm_id=farm_id, cattle_id=data.cattle_id, breeding_event_id=data.breeding_event_id, examined_at=data.examined_at, supersedes_id=data.supersedes_id)
        values = data.model_dump(exclude={"calculate_expected_calving"})
        if data.calculate_expected_calving:
            days = data.gestation_days_used or DEFAULT_GESTATION_DAYS
            values["gestation_days_used"] = days
            values["expected_calving_date"] = estimated_calving(db, farm_id=farm_id, cattle_id=data.cattle_id, breeding_event_id=data.breeding_event_id, examined_at=data.examined_at, gestation_days=days)
        record = PregnancyExamination(farm_id=farm_id, examined_by_id=access.membership.user_id, **values)
        db.add(record); flush(db, "This pregnancy examination request has already been recorded"); audit(db, farm_id=farm_id, entity_type="pregnancy_examination", entity_id=record.id, action=BreedingAuditAction.CLINICAL_ASSESSMENT if not data.supersedes_id else BreedingAuditAction.CORRECTED, summary=f"Veterinarian recorded {record.assessment.value} assessment", actor_id=access.membership.user_id)
        commit(db, "This pregnancy examination request has already been recorded"); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc)


@router.get("/pregnancy-losses", response_model=list[PregnancyLossResponse])
def list_losses(farm_id: UUID, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    return db.scalars(select(PregnancyLoss).where(PregnancyLoss.farm_id == farm_id).order_by(PregnancyLoss.occurred_on.desc())).all()


@router.post("/pregnancy-losses", response_model=PregnancyLossResponse, status_code=201)
def create_loss(farm_id: UUID, data: PregnancyLossCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_veterinarian_permission(Permission.BREEDING_PREGNANCY_ASSESS))):
    try:
        animal = female(db, farm_id, data.cattle_id)
        if animal.date_of_birth and data.occurred_on < animal.date_of_birth: raise BreedingValidationError("Loss date cannot precede the animal's birth")
        if data.occurred_on > date.today(): raise BreedingValidationError("Loss date cannot be in the future")
        if data.pregnancy_examination_id:
            exam = scoped(db, PregnancyExamination, farm_id, data.pregnancy_examination_id)
            if exam.cattle_id != data.cattle_id: raise BreedingValidationError("Pregnancy examination belongs to another animal")
        record = PregnancyLoss(farm_id=farm_id, assessed_by_id=access.membership.user_id, **data.model_dump())
        db.add(record); flush(db, "This pregnancy loss request has already been recorded"); audit(db, farm_id=farm_id, entity_type="pregnancy_loss", entity_id=record.id, action=BreedingAuditAction.CLINICAL_ASSESSMENT, summary=f"Veterinarian recorded {record.loss_type.value.lower()} pregnancy loss", actor_id=access.membership.user_id)
        commit(db, "This pregnancy loss request has already been recorded"); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc)


@router.get("/calvings", response_model=list[CalvingEventResponse])
def list_calvings(farm_id: UUID, dam_id: UUID | None = None, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    q = select(CalvingEvent).where(CalvingEvent.farm_id == farm_id)
    if dam_id: q = q.where(CalvingEvent.dam_id == dam_id)
    return db.scalars(q.order_by(CalvingEvent.calved_at.desc()).limit(500)).all()


@router.post("/calvings", response_model=CalvingEventResponse, status_code=201)
def create_calving(farm_id: UUID, data: CalvingEventCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_CALVING_RECORD))):
    try:
        validate_calving(db, farm_id=farm_id, dam_id=data.dam_id, breeding_event_id=data.breeding_event_id, calved_at=data.calved_at)
        record = CalvingEvent(farm_id=farm_id, recorded_by_id=access.membership.user_id, **data.model_dump())
        db.add(record); flush(db, "This calving request has already been recorded"); audit(db, farm_id=farm_id, entity_type="calving", entity_id=record.id, action=BreedingAuditAction.CREATED, summary="Recorded factual calving observation", actor_id=access.membership.user_id)
        commit(db, "This calving request has already been recorded"); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc)


@router.patch("/calvings/{calving_id}/clinical", response_model=CalvingEventResponse)
def update_calving_clinical(farm_id: UUID, calving_id: UUID, data: CalvingClinicalUpdate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_veterinarian_permission(Permission.BREEDING_PREGNANCY_ASSESS))):
    try:
        prior = scoped(db, CalvingEvent, farm_id, calving_id)
        # Clinical history is append-only: a second signed assessment requires a correction workflow.
        if prior.clinical_recorded_by_id: raise BreedingValidationError("Clinical assessment is signed and cannot be silently overwritten")
        prior.clinical_complications, prior.clinical_diagnosis, prior.post_calving_follow_up_at, prior.clinical_recorded_by_id = data.clinical_complications, data.clinical_diagnosis, data.post_calving_follow_up_at, access.membership.user_id
        audit(db, farm_id=farm_id, entity_type="calving", entity_id=prior.id, action=BreedingAuditAction.CLINICAL_ASSESSMENT, summary="Veterinarian signed calving complication assessment", actor_id=access.membership.user_id)
        db.commit(); db.refresh(prior); return prior
    except BreedingValidationError as exc: invalid(exc, 409 if "signed" in str(exc) else 404)


@router.post("/calvings/{calving_id}/offspring", response_model=OffspringResponse, status_code=201)
def create_offspring(farm_id: UUID, calving_id: UUID, data: OffspringCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_CALVING_RECORD))):
    try:
        event = scoped(db, CalvingEvent, farm_id, calving_id)
        existing = db.scalar(select(CalvingOffspring, Cattle).join(Cattle, Cattle.id == CalvingOffspring.cattle_id).where(CalvingOffspring.farm_id == farm_id, CalvingOffspring.calving_event_id == calving_id, CalvingOffspring.birth_order == data.birth_order))
        if existing: raise BreedingValidationError("This birth order is already registered for the calving")
        link = register_offspring(db, farm_id=farm_id, event=event, data=data, actor_id=access.membership.user_id)
        commit(db, "This offspring registration conflicts with an existing record")
        calf = db.get(Cattle, link.cattle_id)
        return OffspringResponse(id=link.id, cattle_id=calf.id, calving_event_id=event.id, tag_number=calf.tag_number, dam_id=calf.mother_id, sire_id=calf.father_id, birth_order=link.birth_order)
    except BreedingValidationError as exc: invalid(exc, 409 if "already" in str(exc) else 422)


@router.post("/parentage", response_model=ParentageResponse, status_code=201)
def create_parentage(farm_id: UUID, data: ParentageCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_PEDIGREE_MANAGE))):
    try:
        record = assign_parentage(db, farm_id=farm_id, data=data, actor_id=access.membership.user_id)
        commit(db, "This parentage request has already been recorded"); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc)


@router.get("/pedigree/{cattle_id}", response_model=PedigreeResponse)
def get_pedigree(farm_id: UUID, cattle_id: UUID, generations: int = Query(3, ge=1, le=6), db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    try:
        subject, ancestors, incomplete = pedigree(db, farm_id=farm_id, cattle_id=cattle_id, generations=generations)
        return PedigreeResponse(subject=subject, ancestors=ancestors, incomplete=incomplete)
    except BreedingValidationError as exc: invalid(exc, 404)


@router.get("/reminders", response_model=list[ReminderResponse])
def list_reminders(farm_id: UUID, status_filter: ReminderStatus | None = Query(None, alias="status"), db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    q = select(BreedingReminder).where(BreedingReminder.farm_id == farm_id)
    if status_filter: q = q.where(BreedingReminder.status == status_filter)
    # Workers see reminders assigned to them or unassigned farm work.
    if access.membership.role.value == "WORKER": q = q.where((BreedingReminder.assigned_to_id.is_(None)) | (BreedingReminder.assigned_to_id == access.membership.user_id))
    return db.scalars(q.order_by(BreedingReminder.due_at).limit(500)).all()


@router.post("/reminders", response_model=ReminderResponse, status_code=201)
def create_reminder(farm_id: UUID, data: ReminderCreate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_MANAGE))):
    try:
        female(db, farm_id, data.cattle_id)
        if data.assigned_to_id and not member_exists(db, farm_id, data.assigned_to_id): raise BreedingValidationError("Assigned user is not an active farm member")
        record = BreedingReminder(farm_id=farm_id, created_by_id=access.membership.user_id, **data.model_dump())
        db.add(record); commit(db, "This reminder request has already been recorded"); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc)


@router.patch("/reminders/{reminder_id}", response_model=ReminderResponse)
def update_reminder(farm_id: UUID, reminder_id: UUID, data: ReminderUpdate, db: Session = Depends(get_db), access: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    try:
        record = scoped(db, BreedingReminder, farm_id, reminder_id)
        if access.membership.role.value == "WORKER" and record.assigned_to_id not in {None, access.membership.user_id}: raise BreedingValidationError("This reminder is assigned to another user")
        record.status = data.status; db.commit(); db.refresh(record); return record
    except BreedingValidationError as exc: invalid(exc, 403 if "another user" in str(exc) else 404)


@router.get("/reports/summary", response_model=BreedingReportResponse)
def report(farm_id: UUID, date_from: date, date_to: date, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_REPORTS_VIEW))):
    if date_to < date_from or (date_to - date_from).days > 366: raise HTTPException(422, "Date range must be ordered and no longer than 366 days")
    start, end = datetime.combine(date_from, datetime.min.time(), timezone.utc), datetime.combine(date_to + timedelta(days=1), datetime.min.time(), timezone.utc)
    events = db.scalar(select(func.count(BreedingEvent.id)).where(BreedingEvent.farm_id == farm_id, BreedingEvent.scheduled_at >= start, BreedingEvent.scheduled_at < end)) or 0
    completed = db.scalar(select(func.count(BreedingEvent.id)).where(BreedingEvent.farm_id == farm_id, BreedingEvent.status == BreedingEventStatus.COMPLETED, BreedingEvent.scheduled_at >= start, BreedingEvent.scheduled_at < end)) or 0
    pregnant = db.scalar(select(func.count(PregnancyExamination.id)).where(PregnancyExamination.farm_id == farm_id, PregnancyExamination.assessment == PregnancyAssessment.PREGNANT, PregnancyExamination.examined_at >= start, PregnancyExamination.examined_at < end)) or 0
    calvings = db.scalars(select(CalvingEvent).where(CalvingEvent.farm_id == farm_id, CalvingEvent.calved_at >= start, CalvingEvent.calved_at < end)).all()
    rate = (Decimal(pregnant * 100) / Decimal(completed)).quantize(Decimal("0.01")) if completed else None
    return BreedingReportResponse(date_from=date_from, date_to=date_to, breeding_events=events, completed_breedings=completed, confirmed_pregnancies=pregnant, calving_events=len(calvings), live_calves=sum(x.live_count for x in calvings), stillborn_calves=sum(x.stillborn_count for x in calvings), pregnancy_rate_percent=rate, data_note="Pregnancy rate is based only on recorded completed breedings and confirmed exams in this period; missing follow-up data can bias it." if completed else "Insufficient completed breeding data for a pregnancy rate.")


@router.get("/audit")
def audit_history(farm_id: UUID, entity_id: UUID | None = None, db: Session = Depends(get_db), _: FarmAccess = Depends(require_farm_permission(Permission.BREEDING_VIEW))):
    q = select(BreedingAuditEvent).where(BreedingAuditEvent.farm_id == farm_id)
    if entity_id: q = q.where(BreedingAuditEvent.entity_id == entity_id)
    rows = db.scalars(q.order_by(BreedingAuditEvent.created_at.desc()).limit(500)).all()
    return [{"id": str(row.id), "entity_type": row.entity_type, "entity_id": str(row.entity_id), "action": row.action.value, "summary": row.summary, "actor_id": str(row.actor_id), "created_at": row.created_at} for row in rows]
