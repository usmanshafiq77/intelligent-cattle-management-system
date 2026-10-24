"""Add farm tasks, worker assignments and notifications.

Revision ID: a2c4e6f8b108
Revises: f1a3b5c7d906
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a2c4e6f8b108"
down_revision = "f1a3b5c7d906"
branch_labels = None
depends_on = None

PERMISSIONS = ["task.view", "task.manage", "task.update.assigned", "cattle.assignment.manage", "notification.view"]
ENUMS = {
    "task_category": ["GENERAL", "HEALTH", "VACCINATION", "BREEDING", "FEEDING", "MILKING", "MAINTENANCE"],
    "task_priority": ["LOW", "MEDIUM", "HIGH", "URGENT"],
    "operational_task_status": ["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"],
    "task_recurrence_kind": ["NONE", "DAILY", "WEEKLY", "MONTHLY"],
}

def U(): return postgresql.UUID(as_uuid=True)
def E(name): return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)

def upgrade():
    bind = op.get_bind()
    for name, values in ENUMS.items(): postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.execute(sa.text("INSERT INTO permissions (code) SELECT code FROM unnest(CAST(:codes AS text[])) code ON CONFLICT (code) DO NOTHING").bindparams(codes=PERMISSIONS))
    op.create_table("operational_tasks",
        sa.Column("id", U(), primary_key=True), sa.Column("farm_id", U(), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False), sa.Column("description", sa.Text()), sa.Column("category", E("task_category"), nullable=False),
        sa.Column("priority", E("task_priority"), server_default="MEDIUM", nullable=False), sa.Column("status", E("operational_task_status"), server_default="OPEN", nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)), sa.Column("cattle_id", U()), sa.Column("created_by_id", U(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("recurrence_kind", E("task_recurrence_kind"), server_default="NONE", nullable=False), sa.Column("recurrence_interval", sa.Integer(), server_default="1", nullable=False),
        sa.Column("recurrence_until", sa.DateTime(timezone=True)), sa.Column("source_task_id", U(), sa.ForeignKey("operational_tasks.id", ondelete="SET NULL")),
        sa.Column("client_request_id", U(), nullable=False), sa.Column("version", sa.Integer(), server_default="1", nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_operational_task_cattle_scope"),
        sa.UniqueConstraint("id", "farm_id", name="uq_operational_task_scope"), sa.UniqueConstraint("farm_id", "client_request_id", name="uq_operational_task_request"),
        sa.CheckConstraint("version > 0", name="ck_operational_task_version"), sa.CheckConstraint("recurrence_interval > 0", name="ck_operational_task_recurrence_interval"))
    op.create_index("ix_operational_task_farm_due", "operational_tasks", ["farm_id", "status", "due_at"])
    op.create_table("task_assignments",
        sa.Column("id", U(), primary_key=True), sa.Column("task_id", U(), sa.ForeignKey("operational_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", U(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("assigned_by_id", U(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("task_id", "user_id", name="uq_task_assignment_user"))
    op.create_index("ix_task_assignment_user", "task_assignments", ["user_id", "revoked_at"])
    op.create_table("worker_cattle_assignments",
        sa.Column("id", U(), primary_key=True), sa.Column("farm_id", U(), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("worker_id", U(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("cattle_id", U(), nullable=False),
        sa.Column("assigned_by_id", U(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="CASCADE", name="fk_worker_cattle_scope"),
        sa.UniqueConstraint("farm_id", "worker_id", "cattle_id", name="uq_worker_cattle_assignment"))
    op.create_index("ix_worker_cattle_active", "worker_cattle_assignments", ["farm_id", "worker_id", "ended_at"])
    op.create_table("task_activities",
        sa.Column("id", U(), primary_key=True), sa.Column("task_id", U(), sa.ForeignKey("operational_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_user_id", U(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("action", sa.String(40), nullable=False),
        sa.Column("previous_status", E("operational_task_status")), sa.Column("new_status", E("operational_task_status")), sa.Column("note", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_task_activities_task_id", "task_activities", ["task_id"])
    op.create_table("app_notifications",
        sa.Column("id", U(), primary_key=True), sa.Column("user_id", U(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("farm_id", U(), sa.ForeignKey("farms.id", ondelete="CASCADE")),
        sa.Column("category", sa.String(40), nullable=False), sa.Column("title", sa.String(160), nullable=False), sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("source_type", sa.String(50)), sa.Column("source_id", U()), sa.Column("route", sa.String(300)), sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_app_notification_key"))
    op.create_index("ix_app_notification_inbox", "app_notifications", ["user_id", "read_at", "created_at"])
    op.create_table("notification_preferences",
        sa.Column("user_id", U(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True), sa.Column("in_app_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default="false", nullable=False), sa.Column("push_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("reminder_lead_minutes", sa.Integer(), server_default="1440", nullable=False), sa.Column("quiet_hours_start", sa.String(5)), sa.Column("quiet_hours_end", sa.String(5)),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False), sa.Column("category_settings", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.CheckConstraint("reminder_lead_minutes BETWEEN 0 AND 10080", name="ck_notification_lead_minutes"))
    op.create_table("notification_delivery_attempts",
        sa.Column("id", U(), primary_key=True), sa.Column("notification_id", U(), sa.ForeignKey("app_notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("error", sa.String(500)),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_notification_delivery_attempts_notification_id", "notification_delivery_attempts", ["notification_id"])

def downgrade():
    for table in ["notification_delivery_attempts", "notification_preferences", "app_notifications", "task_activities", "worker_cattle_assignments", "task_assignments", "operational_tasks"]: op.drop_table(table)
    op.execute(sa.text("DELETE FROM permissions WHERE code = ANY(CAST(:codes AS text[]))").bindparams(codes=PERMISSIONS))
    bind = op.get_bind()
    for name, values in reversed(list(ENUMS.items())): postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
