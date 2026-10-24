"""Idempotent reminder generation for a separately scheduled worker.

This module never sends external messages. Deployments may call
``generate_due_task_notifications`` from their existing job runner.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.breeding import BreedingReminder, ReminderStatus
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.feed import FeedItem, FeedingSchedule
from app.models.health import VaccinationSchedule, VaccinationScheduleStatus
from app.models.work_management import AppNotification, OperationalTask, TaskAssignment, TaskStatus


LOCK_KEY = 624_817_306


def _farm_leads(db: Session, farm_id):
    return list(db.scalars(select(FarmMember.user_id).where(FarmMember.farm_id == farm_id, FarmMember.status == MemberStatus.ACTIVE, FarmMember.role.in_([FarmRole.FARM_OWNER, FarmRole.FARM_MANAGER]))))


def _add(db: Session, *, recipients, farm_id, category, title, message, source_type, source_id, route, key) -> int:
    count = 0
    for user_id in set(recipients):
        with db.begin_nested():
            try:
                db.add(AppNotification(user_id=user_id, farm_id=farm_id, category=category, title=title, message=message, source_type=source_type, source_id=source_id, route=route, idempotency_key=key)); db.flush(); count += 1
            except IntegrityError: pass
    return count


def generate_due_task_notifications(db: Session, *, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_KEY}):
        return 0
    window_end = now + timedelta(hours=24)
    tasks = db.scalars(
        select(OperationalTask).where(
            OperationalTask.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
            OperationalTask.due_at.is_not(None),
            OperationalTask.due_at <= window_end,
        )
    ).all()
    created = 0
    for task in tasks:
        event = "overdue" if task.due_at < now else "due"
        for user_id in db.scalars(select(TaskAssignment.user_id).where(TaskAssignment.task_id == task.id, TaskAssignment.revoked_at.is_(None))):
            key = f"task-{event}:{task.id}:{task.due_at.isoformat()}"
            with db.begin_nested():
                try:
                    db.add(AppNotification(user_id=user_id, farm_id=task.farm_id, category="TASK", title="Task overdue" if event == "overdue" else "Task due soon", message=task.title, source_type="TASK", source_id=task.id, route=f"/tasks/{task.id}", idempotency_key=key))
                    db.flush(); created += 1
                except IntegrityError:
                    pass
    db.commit()
    return created


def generate_authoritative_module_notifications(db: Session, *, now: datetime | None = None) -> int:
    """Create alerts only from persisted module schedules and thresholds."""
    now = now or datetime.now(timezone.utc)
    if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": LOCK_KEY + 1}): return 0
    created = 0
    horizon = (now + timedelta(hours=24)).date()
    vaccinations = db.scalars(select(VaccinationSchedule).where(VaccinationSchedule.status == VaccinationScheduleStatus.SCHEDULED, VaccinationSchedule.due_date <= horizon)).all()
    for item in vaccinations:
        recipients = [item.responsible_user_id] if item.responsible_user_id else _farm_leads(db, item.farm_id)
        created += _add(db, recipients=recipients, farm_id=item.farm_id, category="VACCINATION", title="Vaccination due", message=f"{item.vaccine_name} is due {item.due_date.isoformat()}", source_type="VACCINATION_SCHEDULE", source_id=item.id, route="/vaccinations", key=f"vaccination-due:{item.id}:{item.due_date}")
    breeding = db.scalars(select(BreedingReminder).where(BreedingReminder.status == ReminderStatus.OPEN, BreedingReminder.due_at <= now + timedelta(hours=24))).all()
    for item in breeding:
        recipients = [item.assigned_to_id] if item.assigned_to_id else _farm_leads(db, item.farm_id)
        created += _add(db, recipients=recipients, farm_id=item.farm_id, category="BREEDING", title=item.title, message="Estimated reminder" if item.is_estimate else "Breeding reminder due", source_type="BREEDING_REMINDER", source_id=item.id, route="/breeding/reminders", key=f"breeding-due:{item.id}:{item.due_at.isoformat()}")
    low_stock = db.scalars(select(FeedItem).where(FeedItem.is_active.is_(True), FeedItem.current_quantity <= FeedItem.reorder_level)).all()
    for item in low_stock:
        created += _add(db, recipients=_farm_leads(db, item.farm_id), farm_id=item.farm_id, category="FEED", title="Low feed stock", message=f"{item.name} is at or below its configured reorder level", source_type="FEED_ITEM", source_id=item.id, route="/feed/low-stock", key=f"feed-low:{item.id}:{item.updated_at.isoformat() if item.updated_at else item.current_quantity}")
    schedules = db.scalars(select(FeedingSchedule).where(FeedingSchedule.is_active.is_(True), FeedingSchedule.start_date <= now.date(), (FeedingSchedule.end_date.is_(None) | (FeedingSchedule.end_date >= now.date())))).all()
    for item in schedules:
        created += _add(db, recipients=_farm_leads(db, item.farm_id), farm_id=item.farm_id, category="FEED", title="Feeding scheduled", message=f"{item.name} at {item.feeding_time.isoformat(timespec='minutes')}", source_type="FEEDING_SCHEDULE", source_id=item.id, route="/feed/schedules", key=f"feeding:{item.id}:{now.date().isoformat()}")
    db.commit()
    return created


def generate_all_notifications(db: Session, *, now: datetime | None = None) -> int:
    return generate_due_task_notifications(db, now=now) + generate_authoritative_module_notifications(db, now=now)
