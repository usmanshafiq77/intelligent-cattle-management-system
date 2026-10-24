"""add user/farm settings and encrypted cloud backup metadata

Revision ID: b3d5f7a9c210
Revises: a2c4e6f8b108
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b3d5f7a9c210"
down_revision = "a2c4e6f8b108"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("phone", sa.String(32)), sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"), sa.Column("date_format", sa.String(20), nullable=False, server_default="YYYY-MM-DD"),
        sa.Column("time_format", sa.String(10), nullable=False, server_default="24H"), sa.Column("theme", sa.String(20), nullable=False, server_default="emerald"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("language = 'en'", name="ck_user_preferences_supported_language"), sa.CheckConstraint("theme IN ('emerald','midnight','indigo')", name="ck_user_preferences_theme"), sa.CheckConstraint("time_format IN ('12H','24H')", name="ck_user_preferences_time_format"))
    op.create_table("pending_email_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("new_email", sa.String(255), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("used_at", sa.DateTime(timezone=True)), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("token_hash", name="uq_pending_email_change_token"))
    op.create_index("uq_pending_email_change_active_user", "pending_email_changes", ["user_id"], unique=True, postgresql_where=sa.text("used_at IS NULL AND revoked_at IS NULL"))
    op.create_table("security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False), sa.Column("summary", sa.String(500), nullable=False), sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_security_events_user_id", "security_events", ["user_id"])
    op.create_table("account_deletion_requests",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True), sa.Column("status", sa.String(20), nullable=False, server_default="REQUESTED"),
        sa.Column("reason", sa.String(1000)), sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('REQUESTED','CANCELLED','REVIEWED')", name="ck_account_deletion_status"))
    op.create_table("farm_preferences",
        sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="CASCADE"), primary_key=True), sa.Column("contact_email", sa.String(255)), sa.Column("contact_phone", sa.String(32)), sa.Column("address", sa.String(500)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"), sa.Column("measurement_system", sa.String(10), nullable=False, server_default="METRIC"), sa.Column("milk_volume_unit", sa.String(10), nullable=False, server_default="LITER"), sa.Column("feed_weight_unit", sa.String(10), nullable=False, server_default="KG"),
        sa.Column("notification_settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("operational_settings", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("measurement_system IN ('METRIC','IMPERIAL')", name="ck_farm_preferences_measurement"), sa.CheckConstraint("milk_volume_unit IN ('LITER','GALLON')", name="ck_farm_preferences_milk_unit"), sa.CheckConstraint("feed_weight_unit IN ('KG','LB')", name="ck_farm_preferences_feed_unit"))
    op.create_table("google_drive_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("provider", sa.String(20), nullable=False, server_default="GOOGLE_DRIVE", unique=True),
        sa.Column("encrypted_refresh_token", sa.LargeBinary(), nullable=False), sa.Column("encrypted_access_token", sa.LargeBinary()), sa.Column("token_expires_at", sa.DateTime(timezone=True)), sa.Column("scope", sa.String(500), nullable=False), sa.Column("folder_id", sa.String(200)),
        sa.Column("connected_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("provider = 'GOOGLE_DRIVE'", name="ck_google_drive_provider"))
    op.create_table("backup_configuration",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("daily_time", sa.Time(), nullable=False, server_default="02:00:00"), sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("keep_daily", sa.Integer(), nullable=False, server_default="7"), sa.Column("keep_weekly", sa.Integer(), nullable=False, server_default="4"), sa.Column("include_media", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_backup_configuration_singleton"), sa.CheckConstraint("keep_daily BETWEEN 1 AND 365 AND keep_weekly BETWEEN 1 AND 104", name="ck_backup_retention_range"))
    op.create_table("backup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("backup_type", sa.String(20), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("file_name", sa.String(255)), sa.Column("size_bytes", sa.BigInteger()), sa.Column("plaintext_sha256", sa.String(64)), sa.Column("encrypted_sha256", sa.String(64)), sa.Column("drive_file_id", sa.String(200)),
        sa.Column("local_available", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("integrity_verified", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("error_code", sa.String(50)), sa.Column("error_summary", sa.String(500)),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"), sa.Column("next_attempt_at", sa.DateTime(timezone=True)), sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("requested_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("backup_type IN ('ON_DEMAND','DAILY','WEEKLY')", name="ck_backup_job_type"),
        sa.CheckConstraint("status IN ('PENDING','RUNNING','RETRY_PENDING','COMPLETED_LOCALLY','UPLOAD_PENDING','VERIFIED','FAILED','RESTORE_TESTED')", name="ck_backup_job_status"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempt_count <= max_attempts", name="ck_backup_job_attempts"),
        sa.UniqueConstraint("request_id", name="uq_backup_job_request"))
    op.create_index("ix_backup_job_status_created", "backup_jobs", ["status", "created_at"])
    op.create_table("restore_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("backup_job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("backup_jobs.id", ondelete="RESTRICT"), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("destination", sa.String(100), nullable=False),
        sa.Column("report_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("error_summary", sa.String(500)), sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('RUNNING','PASSED','FAILED')", name="ck_restore_verification_status"))
    op.create_index("ix_restore_verifications_backup_job_id", "restore_verifications", ["backup_job_id"])


def downgrade():
    for table in ["restore_verifications", "backup_jobs", "backup_configuration", "google_drive_credentials", "farm_preferences", "account_deletion_requests", "security_events", "pending_email_changes", "user_preferences"]:
        op.drop_table(table)
