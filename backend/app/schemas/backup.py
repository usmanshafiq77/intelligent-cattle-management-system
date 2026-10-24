from datetime import datetime, time
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class BackupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    current_password: str = Field(min_length=1, max_length=128)
    backup_type: str = Field(default="ON_DEMAND", pattern=r"^(ON_DEMAND|DAILY|WEEKLY)$")


class BackupJobResponse(BaseModel):
    id: UUID
    request_id: UUID
    backup_type: str
    status: str
    file_name: str | None
    size_bytes: int | None
    encrypted_sha256: str | None
    drive_file_id: str | None
    local_available: bool
    integrity_verified: bool
    error_code: str | None
    error_summary: str | None
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None
    metadata_json: dict
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BackupConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule_enabled: bool = False
    daily_time: time = time(2, 0)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    keep_daily: int = Field(default=7, ge=1, le=365)
    keep_weekly: int = Field(default=4, ge=1, le=104)
    include_media: bool = False

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError: raise ValueError("Unknown IANA timezone") from None
        return value

    @field_validator("include_media")
    @classmethod
    def media_backup_not_yet_supported(cls, value):
        if value: raise ValueError("Media backup is not implemented; keep include_media disabled")
        return value


class BackupConfigResponse(BackupConfigUpdate):
    id: int
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BackupConfigChange(BackupConfigUpdate):
    current_password: str = Field(min_length=1, max_length=128)


class ReauthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)


class RestoreTestRequest(ReauthRequest):
    destination_database: str = Field(min_length=6, max_length=63, pattern=r"^[A-Za-z0-9_]+$")
