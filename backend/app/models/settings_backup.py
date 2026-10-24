import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, BigInteger, String, Text, Time, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    date_format: Mapped[str] = mapped_column(String(20), nullable=False, default="YYYY-MM-DD")
    time_format: Mapped[str] = mapped_column(String(10), nullable=False, default="24H")
    theme: Mapped[str] = mapped_column(String(20), nullable=False, default="emerald")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (CheckConstraint("language = 'en'", name="ck_user_preferences_supported_language"), CheckConstraint("theme IN ('emerald','midnight','indigo')", name="ck_user_preferences_theme"), CheckConstraint("time_format IN ('12H','24H')", name="ck_user_preferences_time_format"))


class PendingEmailChange(Base):
    __tablename__ = "pending_email_changes"
    __table_args__ = (UniqueConstraint("token_hash", name="uq_pending_email_change_token"), Index("uq_pending_email_change_active_user", "user_id", unique=True, postgresql_where=text("used_at IS NULL AND revoked_at IS NULL")))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    new_email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SecurityEvent(Base):
    __tablename__ = "security_events"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AccountDeletionRequest(Base):
    __tablename__ = "account_deletion_requests"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="REQUESTED")
    reason: Mapped[str | None] = mapped_column(String(1000))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("status IN ('REQUESTED','CANCELLED','REVIEWED')", name="ck_account_deletion_status"),)


class FarmPreference(Base):
    __tablename__ = "farm_preferences"
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    measurement_system: Mapped[str] = mapped_column(String(10), nullable=False, default="METRIC")
    milk_volume_unit: Mapped[str] = mapped_column(String(10), nullable=False, default="LITER")
    feed_weight_unit: Mapped[str] = mapped_column(String(10), nullable=False, default="KG")
    notification_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    operational_settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (CheckConstraint("measurement_system IN ('METRIC','IMPERIAL')", name="ck_farm_preferences_measurement"), CheckConstraint("milk_volume_unit IN ('LITER','GALLON')", name="ck_farm_preferences_milk_unit"), CheckConstraint("feed_weight_unit IN ('KG','LB')", name="ck_farm_preferences_feed_unit"))


class GoogleDriveCredential(Base):
    __tablename__ = "google_drive_credentials"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="GOOGLE_DRIVE", unique=True)
    encrypted_refresh_token: Mapped[bytes] = mapped_column(nullable=False)
    encrypted_access_token: Mapped[bytes | None] = mapped_column()
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scope: Mapped[str] = mapped_column(String(500), nullable=False)
    folder_id: Mapped[str | None] = mapped_column(String(200))
    connected_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("provider = 'GOOGLE_DRIVE'", name="ck_google_drive_provider"),)


class BackupConfiguration(Base):
    __tablename__ = "backup_configuration"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    daily_time: Mapped[time] = mapped_column(Time, nullable=False, default=time(2, 0))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    keep_daily: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    keep_weekly: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    include_media: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    __table_args__ = (CheckConstraint("id = 1", name="ck_backup_configuration_singleton"), CheckConstraint("keep_daily BETWEEN 1 AND 365 AND keep_weekly BETWEEN 1 AND 104", name="ck_backup_retention_range"))


class BackupJob(Base):
    __tablename__ = "backup_jobs"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_backup_job_request"),
        Index("ix_backup_job_status_created", "status", "created_at"),
        CheckConstraint("backup_type IN ('ON_DEMAND','DAILY','WEEKLY')", name="ck_backup_job_type"),
        CheckConstraint("status IN ('PENDING','RUNNING','RETRY_PENDING','COMPLETED_LOCALLY','UPLOAD_PENDING','VERIFIED','FAILED','RESTORE_TESTED')", name="ck_backup_job_status"),
        CheckConstraint("attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempt_count <= max_attempts", name="ck_backup_job_attempts"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    backup_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    file_name: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    plaintext_sha256: Mapped[str | None] = mapped_column(String(64))
    encrypted_sha256: Mapped[str | None] = mapped_column(String(64))
    drive_file_id: Mapped[str | None] = mapped_column(String(200))
    local_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    integrity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_summary: Mapped[str | None] = mapped_column(String(500))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RestoreVerification(Base):
    __tablename__ = "restore_verifications"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    backup_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("backup_jobs.id", ondelete="RESTRICT"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    destination: Mapped[str] = mapped_column(String(100), nullable=False)
    report_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(String(500))
    verified_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("status IN ('RUNNING','PASSED','FAILED')", name="ck_restore_verification_status"),)
