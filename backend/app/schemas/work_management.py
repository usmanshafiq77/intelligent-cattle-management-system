from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.work_management import RecurrenceKind, TaskCategory, TaskPriority, TaskStatus


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskCreate(StrictRequest):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    category: TaskCategory = TaskCategory.GENERAL
    priority: TaskPriority = TaskPriority.MEDIUM
    due_at: datetime | None = None
    cattle_id: UUID | None = None
    assignee_ids: list[UUID] = Field(default_factory=list, max_length=50)
    recurrence_kind: RecurrenceKind = RecurrenceKind.NONE
    recurrence_interval: int = Field(default=1, ge=1, le=365)
    recurrence_until: datetime | None = None
    client_request_id: UUID

    @field_validator("title", "description")
    @classmethod
    def clean_text(cls, value):
        if value is None:
            return None
        result = " ".join(value.split())
        if not result:
            raise ValueError("Value cannot be blank")
        return result

    @field_validator("due_at", "recurrence_until")
    @classmethod
    def require_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Datetime must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_recurrence(self):
        if self.recurrence_kind == RecurrenceKind.NONE and self.recurrence_until is not None:
            raise ValueError("recurrence_until requires a recurring task")
        return self


class TaskUpdate(StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    category: TaskCategory | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    cattle_id: UUID | None = None
    expected_version: int = Field(ge=1)

    @field_validator("due_at")
    @classmethod
    def require_due_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("Datetime must include a timezone")
        return value


class TaskStatusUpdate(StrictRequest):
    status: TaskStatus
    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=2000)


class TaskAssign(StrictRequest):
    assignee_ids: list[UUID] = Field(min_length=1, max_length=50)


class TaskComment(StrictRequest):
    note: str = Field(min_length=1, max_length=2000)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    title: str
    description: str | None
    category: TaskCategory
    priority: TaskPriority
    status: TaskStatus
    due_at: datetime | None
    cattle_id: UUID | None
    created_by_id: UUID
    recurrence_kind: RecurrenceKind
    recurrence_interval: int
    recurrence_until: datetime | None
    version: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    assignee_ids: list[UUID] = Field(default_factory=list)
    is_overdue: bool = False


class WorkerCattleCreate(StrictRequest):
    worker_id: UUID
    cattle_id: UUID


class WorkerCattleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    farm_id: UUID
    worker_id: UUID
    cattle_id: UUID
    assigned_by_id: UUID
    assigned_at: datetime
    ended_at: datetime | None


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    farm_id: UUID | None
    category: str
    title: str
    message: str
    source_type: str | None
    source_id: UUID | None
    route: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    items: list[NotificationResponse]
    total: int
    unread: int


class NotificationPreferenceUpdate(StrictRequest):
    in_app_enabled: bool = True
    email_enabled: bool = False
    push_enabled: bool = False
    reminder_lead_minutes: int = Field(default=1440, ge=0, le=10080)
    quiet_hours_start: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    quiet_hours_end: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    category_settings: dict[str, bool] = Field(default_factory=dict)


class NotificationPreferenceResponse(NotificationPreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)
    user_id: UUID
    updated_at: datetime
