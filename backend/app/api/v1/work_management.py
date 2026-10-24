import calendar
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import get_effective_permissions, require_farm_permission
from app.api.v1.auth import get_current_user
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.cattle import Cattle
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.user import User
from app.models.work_management import AppNotification, NotificationPreference, OperationalTask, RecurrenceKind, TaskActivity, TaskAssignment, TaskStatus, WorkerCattleAssignment
from app.schemas.work_management import NotificationList, NotificationPreferenceResponse, NotificationPreferenceUpdate, NotificationResponse, TaskAssign, TaskComment, TaskCreate, TaskResponse, TaskStatusUpdate, TaskUpdate, WorkerCattleCreate, WorkerCattleResponse


router = APIRouter(tags=["Tasks and Notifications"])
farm_router = APIRouter(prefix="/farms/{farm_id}/work")
notification_router = APIRouter(prefix="/notifications")


def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The request conflicts with an existing record") from None


def _assignees(db: Session, task_id: UUID) -> list[UUID]:
    return list(db.scalars(select(TaskAssignment.user_id).where(TaskAssignment.task_id == task_id, TaskAssignment.revoked_at.is_(None))))


def _response(db: Session, item: OperationalTask) -> TaskResponse:
    now = datetime.now(timezone.utc)
    return TaskResponse.model_validate(item).model_copy(update={"assignee_ids": _assignees(db, item.id), "is_overdue": bool(item.due_at and item.due_at < now and item.status not in {TaskStatus.COMPLETED, TaskStatus.CANCELLED})})


def _scoped_task(db: Session, farm_id: UUID, task_id: UUID, *, lock: bool = False) -> OperationalTask:
    query = select(OperationalTask).where(OperationalTask.id == task_id, OperationalTask.farm_id == farm_id)
    if lock:
        query = query.with_for_update()
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return item


def _validate_members(db: Session, farm_id: UUID, user_ids: list[UUID]):
    unique_ids = set(user_ids)
    found = set(db.scalars(select(FarmMember.user_id).where(FarmMember.farm_id == farm_id, FarmMember.user_id.in_(unique_ids), FarmMember.status == MemberStatus.ACTIVE)))
    if found != unique_ids:
        raise HTTPException(status_code=422, detail="Every assignee must be an active member of this farm")


def _notify_assignment(db: Session, task: OperationalTask, user_id: UUID):
    db.add(AppNotification(user_id=user_id, farm_id=task.farm_id, category="TASK", title="Task assigned", message=task.title, source_type="TASK", source_id=task.id, route=f"/tasks/{task.id}", idempotency_key=f"task-assigned:{task.id}:{user_id}:{task.version}"))


def _next_due(task: OperationalTask) -> datetime | None:
    if not task.due_at or task.recurrence_kind == RecurrenceKind.NONE: return None
    if task.recurrence_kind == RecurrenceKind.DAILY: result = task.due_at + timedelta(days=task.recurrence_interval)
    elif task.recurrence_kind == RecurrenceKind.WEEKLY: result = task.due_at + timedelta(weeks=task.recurrence_interval)
    else:
        month_index = task.due_at.month - 1 + task.recurrence_interval
        year, month = task.due_at.year + month_index // 12, month_index % 12 + 1
        result = task.due_at.replace(year=year, month=month, day=min(task.due_at.day, calendar.monthrange(year, month)[1]))
    return None if task.recurrence_until and result > task.recurrence_until else result


def _create_recurrence(db: Session, task: OperationalTask, actor_id: UUID):
    due = _next_due(task)
    if due is None: return
    request_id = uuid.uuid5(uuid.NAMESPACE_URL, f"icms-task:{task.id}:{due.isoformat()}")
    if db.scalar(select(OperationalTask.id).where(OperationalTask.farm_id == task.farm_id, OperationalTask.client_request_id == request_id)): return
    next_task = OperationalTask(farm_id=task.farm_id, title=task.title, description=task.description, category=task.category, priority=task.priority, due_at=due, cattle_id=task.cattle_id, created_by_id=actor_id, recurrence_kind=task.recurrence_kind, recurrence_interval=task.recurrence_interval, recurrence_until=task.recurrence_until, source_task_id=task.id, client_request_id=request_id)
    db.add(next_task); db.flush()
    for uid in _assignees(db, task.id): db.add(TaskAssignment(task_id=next_task.id, user_id=uid, assigned_by_id=actor_id)); _notify_assignment(db, next_task, uid)
    db.add(TaskActivity(task_id=next_task.id, actor_user_id=actor_id, action="RECURRENCE_CREATED", new_status=TaskStatus.OPEN))


@farm_router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(farm_id: UUID, data: TaskCreate, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_MANAGE)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.scalar(select(OperationalTask).where(OperationalTask.farm_id == farm_id, OperationalTask.client_request_id == data.client_request_id))
    if existing:
        return _response(db, existing)
    if data.cattle_id and db.scalar(select(Cattle.id).where(Cattle.id == data.cattle_id, Cattle.farm_id == farm_id)) is None:
        raise HTTPException(status_code=422, detail="Cattle does not belong to this farm")
    _validate_members(db, farm_id, data.assignee_ids)
    task = OperationalTask(farm_id=farm_id, title=data.title, description=data.description, category=data.category, priority=data.priority, due_at=data.due_at, cattle_id=data.cattle_id, created_by_id=user.id, recurrence_kind=data.recurrence_kind, recurrence_interval=data.recurrence_interval, recurrence_until=data.recurrence_until, client_request_id=data.client_request_id)
    db.add(task); db.flush()
    for assignee_id in set(data.assignee_ids):
        db.add(TaskAssignment(task_id=task.id, user_id=assignee_id, assigned_by_id=user.id)); _notify_assignment(db, task, assignee_id)
    db.add(TaskActivity(task_id=task.id, actor_user_id=user.id, action="CREATED", new_status=task.status))
    _commit(db); db.refresh(task)
    return _response(db, task)


@farm_router.get("/tasks", response_model=list[TaskResponse])
def list_tasks(farm_id: UUID, task_status: TaskStatus | None = Query(None, alias="status"), category: str | None = None, priority: str | None = None, assignee_id: UUID | None = None, mine: bool = False, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), access: FarmAccess = Depends(require_farm_permission(Permission.TASK_VIEW)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(OperationalTask).where(OperationalTask.farm_id == farm_id)
    can_manage = Permission.TASK_MANAGE in get_effective_permissions(db, access)
    assignments_joined = False
    if mine or not can_manage:
        query = query.join(TaskAssignment).where(TaskAssignment.user_id == user.id, TaskAssignment.revoked_at.is_(None))
        assignments_joined = True
    if task_status:
        query = query.where(OperationalTask.status == task_status)
    if category: query = query.where(OperationalTask.category == category)
    if priority: query = query.where(OperationalTask.priority == priority)
    if assignee_id:
        if not can_manage and assignee_id != user.id: raise HTTPException(status_code=403, detail="Cannot view another user's tasks")
        if not assignments_joined: query = query.join(TaskAssignment, TaskAssignment.task_id == OperationalTask.id)
        query = query.where(TaskAssignment.user_id == assignee_id, TaskAssignment.revoked_at.is_(None))
    rows = db.scalars(query.distinct().order_by(OperationalTask.due_at.asc().nullslast(), OperationalTask.created_at.desc()).offset(offset).limit(limit)).all()
    return [_response(db, row) for row in rows]


@farm_router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(farm_id: UUID, task_id: UUID, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_VIEW)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _scoped_task(db, farm_id, task_id)
    if Permission.TASK_MANAGE not in get_effective_permissions(db, access) and user.id not in _assignees(db, task.id):
        raise HTTPException(status_code=404, detail="Task not found")
    return _response(db, task)


@farm_router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(farm_id: UUID, task_id: UUID, data: TaskUpdate, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_MANAGE)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _scoped_task(db, farm_id, task_id, lock=True)
    if task.version != data.expected_version:
        raise HTTPException(status_code=409, detail="Task was updated by another user")
    values = data.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if "cattle_id" in values and values["cattle_id"] and db.scalar(select(Cattle.id).where(Cattle.id == values["cattle_id"], Cattle.farm_id == farm_id)) is None:
        raise HTTPException(status_code=422, detail="Cattle does not belong to this farm")
    for key, value in values.items(): setattr(task, key, value)
    task.version += 1
    db.add(TaskActivity(task_id=task.id, actor_user_id=user.id, action="UPDATED")); _commit(db); db.refresh(task)
    return _response(db, task)


@farm_router.post("/tasks/{task_id}/assign", response_model=TaskResponse)
def assign_task(farm_id: UUID, task_id: UUID, data: TaskAssign, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_MANAGE)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _scoped_task(db, farm_id, task_id, lock=True); _validate_members(db, farm_id, data.assignee_ids)
    now = datetime.now(timezone.utc)
    all_assignments = {x.user_id: x for x in db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == task.id)).all()}
    active = {uid: x for uid, x in all_assignments.items() if x.revoked_at is None}
    desired = set(data.assignee_ids)
    for uid, assignment in active.items():
        if uid not in desired: assignment.revoked_at = now
    for uid in desired - set(active):
        if uid in all_assignments:
            all_assignments[uid].revoked_at = None; all_assignments[uid].assigned_at = now; all_assignments[uid].assigned_by_id = user.id
        else: db.add(TaskAssignment(task_id=task.id, user_id=uid, assigned_by_id=user.id))
        _notify_assignment(db, task, uid)
    task.version += 1; db.add(TaskActivity(task_id=task.id, actor_user_id=user.id, action="REASSIGNED")); _commit(db); db.refresh(task)
    return _response(db, task)


@farm_router.post("/tasks/{task_id}/status", response_model=TaskResponse)
def change_task_status(farm_id: UUID, task_id: UUID, data: TaskStatusUpdate, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_VIEW)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _scoped_task(db, farm_id, task_id, lock=True)
    permissions = get_effective_permissions(db, access)
    if Permission.TASK_MANAGE not in permissions:
        if Permission.TASK_UPDATE_ASSIGNED not in permissions or user.id not in _assignees(db, task.id):
            raise HTTPException(status_code=403, detail="Only an assignee may update this task")
        if data.status not in {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED}:
            raise HTTPException(status_code=403, detail="Assignees may only start or complete tasks")
        allowed = {TaskStatus.OPEN: {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED}, TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED}}
        if data.status not in allowed.get(task.status, set()): raise HTTPException(status_code=422, detail="Invalid task status transition")
    if task.version != data.expected_version: raise HTTPException(status_code=409, detail="Task was updated by another user")
    previous = task.status; task.status = data.status; task.version += 1
    task.completed_at = datetime.now(timezone.utc) if data.status == TaskStatus.COMPLETED else None
    db.add(TaskActivity(task_id=task.id, actor_user_id=user.id, action="STATUS_CHANGED", previous_status=previous, new_status=data.status, note=data.note))
    if data.status == TaskStatus.COMPLETED and previous != TaskStatus.COMPLETED: _create_recurrence(db, task, user.id)
    _commit(db); db.refresh(task)
    return _response(db, task)


@farm_router.post("/tasks/{task_id}/comments", status_code=201)
def add_task_comment(farm_id: UUID, task_id: UUID, data: TaskComment, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_VIEW)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_task(farm_id, task_id, access, user, db)
    activity = TaskActivity(task_id=task_id, actor_user_id=user.id, action="COMMENT", note=data.note.strip())
    db.add(activity); _commit(db); db.refresh(activity); return activity


@farm_router.get("/tasks/{task_id}/history")
def task_history(farm_id: UUID, task_id: UUID, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_VIEW)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_task(farm_id, task_id, access, user, db)
    return db.scalars(select(TaskActivity).where(TaskActivity.task_id == task_id).order_by(TaskActivity.created_at.desc())).all()


@farm_router.post("/cattle-assignments", response_model=WorkerCattleResponse, status_code=201)
def assign_cattle(farm_id: UUID, data: WorkerCattleCreate, access: FarmAccess = Depends(require_farm_permission(Permission.CATTLE_ASSIGNMENT_MANAGE)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    worker = db.scalar(select(FarmMember).where(FarmMember.farm_id == farm_id, FarmMember.user_id == data.worker_id, FarmMember.status == MemberStatus.ACTIVE, FarmMember.role == FarmRole.WORKER))
    if worker is None: raise HTTPException(status_code=422, detail="Cattle may only be assigned to an active farm worker")
    if db.scalar(select(Cattle.id).where(Cattle.id == data.cattle_id, Cattle.farm_id == farm_id)) is None: raise HTTPException(status_code=422, detail="Cattle does not belong to this farm")
    current = db.scalar(select(WorkerCattleAssignment).where(WorkerCattleAssignment.farm_id == farm_id, WorkerCattleAssignment.worker_id == data.worker_id, WorkerCattleAssignment.cattle_id == data.cattle_id))
    if current:
        if current.ended_at is None: return current
        current.ended_at = None; current.assigned_by_id = user.id; current.assigned_at = datetime.now(timezone.utc)
    else:
        current = WorkerCattleAssignment(farm_id=farm_id, worker_id=data.worker_id, cattle_id=data.cattle_id, assigned_by_id=user.id); db.add(current); db.flush()
    db.add(AppNotification(user_id=data.worker_id, farm_id=farm_id, category="CATTLE_ASSIGNMENT", title="Cattle assigned", message="A farm animal was assigned to your care", source_type="CATTLE", source_id=data.cattle_id, route="/tasks/assigned-cattle", idempotency_key=f"cattle-assigned:{current.id}:{current.assigned_at.isoformat()}"))
    _commit(db); db.refresh(current); return current


@farm_router.get("/cattle-assignments", response_model=list[WorkerCattleResponse])
def list_cattle_assignments(farm_id: UUID, worker_id: UUID | None = None, access: FarmAccess = Depends(require_farm_permission(Permission.TASK_VIEW)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    can_manage = Permission.CATTLE_ASSIGNMENT_MANAGE in get_effective_permissions(db, access)
    target = worker_id if can_manage and worker_id else user.id
    return db.scalars(select(WorkerCattleAssignment).where(WorkerCattleAssignment.farm_id == farm_id, WorkerCattleAssignment.worker_id == target, WorkerCattleAssignment.ended_at.is_(None))).all()


@farm_router.delete("/cattle-assignments/{assignment_id}", status_code=204)
def end_cattle_assignment(farm_id: UUID, assignment_id: UUID, access: FarmAccess = Depends(require_farm_permission(Permission.CATTLE_ASSIGNMENT_MANAGE)), db: Session = Depends(get_db)):
    item = db.scalar(select(WorkerCattleAssignment).where(WorkerCattleAssignment.id == assignment_id, WorkerCattleAssignment.farm_id == farm_id).with_for_update())
    if not item: raise HTTPException(status_code=404, detail="Assignment not found")
    item.ended_at = datetime.now(timezone.utc); _commit(db)


@notification_router.get("", response_model=NotificationList)
def list_notifications(farm_id: UUID | None = None, unread_only: bool = False, category: str | None = None, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    base = select(AppNotification).where(AppNotification.user_id == user.id)
    if farm_id:
        membership = db.scalar(select(FarmMember.id).where(FarmMember.farm_id == farm_id, FarmMember.user_id == user.id, FarmMember.status == MemberStatus.ACTIVE))
        if membership is None: raise HTTPException(status_code=404, detail="Farm not found")
        base = base.where(AppNotification.farm_id == farm_id)
    if unread_only: base = base.where(AppNotification.read_at.is_(None))
    if category: base = base.where(AppNotification.category == category)
    items = db.scalars(base.order_by(AppNotification.created_at.desc()).offset(offset).limit(limit)).all()
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    unread_query = select(func.count()).select_from(AppNotification).where(AppNotification.user_id == user.id, AppNotification.read_at.is_(None))
    if farm_id: unread_query = unread_query.where(AppNotification.farm_id == farm_id)
    unread = db.scalar(unread_query) or 0
    return NotificationList(items=items, total=total, unread=unread)


@notification_router.patch("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(notification_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(AppNotification).where(AppNotification.id == notification_id, AppNotification.user_id == user.id).with_for_update())
    if not item: raise HTTPException(status_code=404, detail="Notification not found")
    item.read_at = item.read_at or datetime.now(timezone.utc); _commit(db); db.refresh(item); return item


@notification_router.post("/read-all")
def mark_all_read(farm_id: UUID | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(AppNotification).where(AppNotification.user_id == user.id, AppNotification.read_at.is_(None))
    if farm_id:
        membership = db.scalar(select(FarmMember.id).where(FarmMember.farm_id == farm_id, FarmMember.user_id == user.id, FarmMember.status == MemberStatus.ACTIVE))
        if membership is None: raise HTTPException(status_code=404, detail="Farm not found")
        query = query.where(AppNotification.farm_id == farm_id)
    now = datetime.now(timezone.utc); items = db.scalars(query).all()
    for item in items: item.read_at = now
    _commit(db); return {"updated": len(items)}


@notification_router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(NotificationPreference, user.id)
    if not item:
        item = NotificationPreference(user_id=user.id); db.add(item); _commit(db); db.refresh(item)
    return item


@notification_router.put("/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(data: NotificationPreferenceUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(NotificationPreference, user.id) or NotificationPreference(user_id=user.id)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.add(item); _commit(db); db.refresh(item); return item


@notification_router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(notification_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(AppNotification).where(AppNotification.id == notification_id, AppNotification.user_id == user.id))
    if not item: raise HTTPException(status_code=404, detail="Notification not found")
    return item


router.include_router(farm_router)
router.include_router(notification_router)
