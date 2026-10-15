"""Add health, veterinary care, and vaccination management.

Revision ID: f7a2b3c4d5e6
Revises: e6f1a2b3c4d5

The upgrade is additive. Existing cattle and farm records are not modified.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f7a2b3c4d5e6"
down_revision = "e6f1a2b3c4d5"
branch_labels = None
depends_on = None


HEALTH_PERMISSIONS = [
    "health.create",
    "health.diagnosis",
    "health.vaccination.manage",
    "health.vaccination.administer",
    "health.treatment.manage",
    "health.medication.administer",
    "health.visit.manage",
    "health.audit.view",
]

encounter_type = postgresql.ENUM(
    "ROUTINE",
    "ILLNESS",
    "INJURY",
    "EMERGENCY",
    "FOLLOW_UP",
    name="health_encounter_type",
    create_type=False,
)
encounter_status = postgresql.ENUM(
    "DRAFT", "FINALIZED", name="health_encounter_status", create_type=False
)
diagnosis_severity = postgresql.ENUM(
    "MILD",
    "MODERATE",
    "SEVERE",
    "CRITICAL",
    name="health_diagnosis_severity",
    create_type=False,
)
diagnosis_status = postgresql.ENUM(
    "SUSPECTED",
    "CONFIRMED",
    "RULED_OUT",
    "RESOLVED",
    name="health_diagnosis_status",
    create_type=False,
)
schedule_status = postgresql.ENUM(
    "SCHEDULED",
    "COMPLETED",
    "CANCELLED",
    name="vaccination_schedule_status",
    create_type=False,
)
treatment_status = postgresql.ENUM(
    "PLANNED",
    "ACTIVE",
    "COMPLETED",
    "STOPPED",
    "CANCELLED",
    name="health_treatment_status",
    create_type=False,
)
visit_status = postgresql.ENUM(
    "REQUESTED",
    "SCHEDULED",
    "COMPLETED",
    "CANCELLED",
    name="veterinary_visit_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        encounter_type,
        encounter_status,
        diagnosis_severity,
        diagnosis_status,
        schedule_status,
        treatment_status,
        visit_status,
    ):
        enum_type.create(bind, checkfirst=True)

    op.execute(
        sa.text(
            "INSERT INTO permissions (code) "
            "SELECT code FROM unnest(CAST(:codes AS text[])) AS code "
            "ON CONFLICT (code) DO NOTHING"
        ).bindparams(codes=HEALTH_PERMISSIONS)
    )

    op.create_table(
        "health_encounters",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("encounter_type", encounter_type, nullable=False),
        sa.Column(
            "status", encounter_status, server_default="DRAFT", nullable=False
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("clinical_observations", sa.Text(), nullable=True),
        sa.Column("professional_name", sa.String(200), nullable=True),
        sa.Column("responsible_user_id", sa.UUID(), nullable=True),
        sa.Column("follow_up_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("follow_up_notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'FINALIZED' AND finalized_at IS NOT NULL) OR "
            "(status = 'DRAFT' AND finalized_at IS NULL)",
            name="ck_health_encounter_finalization",
        ),
        sa.CheckConstraint(
            "follow_up_due_at IS NULL OR follow_up_due_at >= occurred_at",
            name="ck_health_encounter_follow_up_after_event",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_health_encounter_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id", "responsible_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_health_encounter_responsible_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_health_encounter_scope"
        ),
    )
    op.create_index(
        "ix_health_encounter_history",
        "health_encounters",
        ["farm_id", "cattle_id", "occurred_at"],
    )
    op.create_index(
        "ix_health_encounter_farm_status",
        "health_encounters",
        ["farm_id", "status"],
    )

    op.create_table(
        "health_diagnoses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("encounter_id", sa.UUID(), nullable=False),
        sa.Column("condition_name", sa.String(200), nullable=False),
        sa.Column("standardized_code", sa.String(50), nullable=True),
        sa.Column("clinical_signs", sa.Text(), nullable=True),
        sa.Column("severity", diagnosis_severity, nullable=False),
        sa.Column("status", diagnosis_status, nullable=False),
        sa.Column("diagnosed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responsible_user_id", sa.UUID(), nullable=True),
        sa.Column("follow_up_recommendations", sa.Text(), nullable=True),
        sa.Column("clinical_notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(condition_name)) > 0",
            name="ck_health_diagnosis_condition_not_empty",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_health_diagnosis_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["encounter_id", "farm_id", "cattle_id"],
            [
                "health_encounters.id",
                "health_encounters.farm_id",
                "health_encounters.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_health_diagnosis_encounter_scope",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id", "responsible_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_health_diagnosis_responsible_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_health_diagnosis_scope"
        ),
    )
    op.create_index(
        "ix_health_diagnosis_history",
        "health_diagnoses",
        ["farm_id", "cattle_id", "diagnosed_at"],
    )
    op.create_index(
        "ix_health_diagnosis_encounter",
        "health_diagnoses",
        ["encounter_id"],
    )

    op.create_table(
        "vaccination_schedules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("vaccine_name", sa.String(200), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column(
            "status", schedule_status, server_default="SCHEDULED", nullable=False
        ),
        sa.Column("responsible_user_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.CheckConstraint(
            "due_date >= scheduled_date",
            name="ck_vaccination_schedule_due_date",
        ),
        sa.CheckConstraint(
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL AND "
            "cancellation_reason IS NOT NULL) OR "
            "(status <> 'CANCELLED' AND cancelled_at IS NULL)",
            name="ck_vaccination_schedule_cancellation",
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
            "(status <> 'COMPLETED' AND completed_at IS NULL)",
            name="ck_vaccination_schedule_completion",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_schedule_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id", "responsible_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_schedule_responsible_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "farm_id",
            "cattle_id",
            name="uq_vaccination_schedule_scope",
        ),
    )
    op.create_index(
        "ix_vaccination_schedule_due",
        "vaccination_schedules",
        ["farm_id", "status", "due_date"],
    )
    op.create_index(
        "uq_vaccination_schedule_active_item",
        "vaccination_schedules",
        ["farm_id", "cattle_id", sa.text("lower(btrim(vaccine_name))"), "scheduled_date"],
        unique=True,
        postgresql_where=sa.text("status = 'SCHEDULED'"),
    )

    op.create_table(
        "vaccination_administrations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=True),
        sa.Column("vaccine_name", sa.String(200), nullable=False),
        sa.Column("administered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dose", sa.Numeric(10, 3), nullable=False),
        sa.Column("dose_unit", sa.String(30), nullable=False),
        sa.Column("route", sa.String(50), nullable=True),
        sa.Column("batch_lot_number", sa.String(100), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("administered_by_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("follow_up_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_due_date", sa.Date(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("dose > 0", name="ck_vaccination_dose_positive"),
        sa.CheckConstraint(
            "expiry_date IS NULL OR expiry_date >= administered_at::date",
            name="ck_vaccination_not_expired_at_administration",
        ),
        sa.CheckConstraint(
            "follow_up_due_at IS NULL OR follow_up_due_at >= administered_at",
            name="ck_vaccination_follow_up_after_administration",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_administration_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_id", "farm_id", "cattle_id"],
            [
                "vaccination_schedules.id",
                "vaccination_schedules.farm_id",
                "vaccination_schedules.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_vaccination_administration_schedule_scope",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id", "administered_by_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_administration_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id",
            "farm_id",
            "cattle_id",
            name="uq_vaccination_administration_scope",
        ),
        sa.UniqueConstraint(
            "schedule_id", name="uq_vaccination_administration_schedule"
        ),
    )
    op.create_index(
        "ix_vaccination_administration_history",
        "vaccination_administrations",
        ["farm_id", "cattle_id", "administered_at"],
    )
    op.create_index(
        "uq_vaccination_administration_event",
        "vaccination_administrations",
        [
            "farm_id",
            "cattle_id",
            sa.text("lower(btrim(vaccine_name))"),
            "administered_at",
            sa.text("coalesce(batch_lot_number, '')"),
        ],
        unique=True,
    )

    op.create_table(
        "treatment_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("encounter_id", sa.UUID(), nullable=True),
        sa.Column("diagnosis_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("medication_name", sa.String(200), nullable=True),
        sa.Column("dosage_quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("dosage_unit", sa.String(30), nullable=True),
        sa.Column("administration_frequency", sa.String(100), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column(
            "status", treatment_status, server_default="PLANNED", nullable=False
        ),
        sa.Column("prescribed_by_id", sa.UUID(), nullable=True),
        sa.Column("withdrawal_period_days", sa.Integer(), nullable=True),
        sa.Column("withdrawal_notes", sa.String(500), nullable=True),
        sa.Column("follow_up_notes", sa.Text(), nullable=True),
        sa.Column("status_reason", sa.String(500), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_treatment_plan_date_range",
        ),
        sa.CheckConstraint(
            "dosage_quantity IS NULL OR dosage_quantity > 0",
            name="ck_treatment_plan_dosage_positive",
        ),
        sa.CheckConstraint(
            "(dosage_quantity IS NULL) = (dosage_unit IS NULL)",
            name="ck_treatment_plan_dosage_complete",
        ),
        sa.CheckConstraint(
            "withdrawal_period_days IS NULL OR withdrawal_period_days >= 0",
            name="ck_treatment_plan_withdrawal_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_treatment_plan_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["encounter_id", "farm_id", "cattle_id"],
            [
                "health_encounters.id",
                "health_encounters.farm_id",
                "health_encounters.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_treatment_plan_encounter_scope",
        ),
        sa.ForeignKeyConstraint(
            ["diagnosis_id", "farm_id", "cattle_id"],
            [
                "health_diagnoses.id",
                "health_diagnoses.farm_id",
                "health_diagnoses.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_treatment_plan_diagnosis_scope",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id", "prescribed_by_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_treatment_plan_prescriber_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_treatment_plan_scope"
        ),
    )
    op.create_index(
        "ix_treatment_plan_history",
        "treatment_plans",
        ["farm_id", "cattle_id", "start_date"],
    )
    op.create_index(
        "ix_treatment_plan_farm_status",
        "treatment_plans",
        ["farm_id", "status"],
    )

    op.create_table(
        "medication_administrations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("treatment_id", sa.UUID(), nullable=False),
        sa.Column("medication_name", sa.String(200), nullable=False),
        sa.Column("administered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("route", sa.String(50), nullable=True),
        sa.Column("administered_by_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantity > 0", name="ck_medication_administration_quantity"
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_medication_administration_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["treatment_id", "farm_id", "cattle_id"],
            [
                "treatment_plans.id",
                "treatment_plans.farm_id",
                "treatment_plans.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_medication_administration_treatment_scope",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id", "administered_by_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_medication_administration_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "treatment_id",
            "administered_at",
            name="uq_medication_administration_event",
        ),
    )
    op.create_index(
        "ix_medication_administration_history",
        "medication_administrations",
        ["farm_id", "cattle_id", "administered_at"],
    )

    op.create_table(
        "veterinary_visits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", visit_status, server_default="REQUESTED", nullable=False
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("veterinarian_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("clinical_notes", sa.Text(), nullable=True),
        sa.Column("follow_up_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("follow_up_notes", sa.Text(), nullable=True),
        sa.Column("cancellation_reason", sa.String(500), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actual_at IS NULL OR actual_at >= requested_at",
            name="ck_veterinary_visit_actual_after_request",
        ),
        sa.CheckConstraint(
            "follow_up_due_at IS NULL OR "
            "(actual_at IS NOT NULL AND follow_up_due_at >= actual_at)",
            name="ck_veterinary_visit_follow_up",
        ),
        sa.CheckConstraint(
            "(status = 'COMPLETED' AND actual_at IS NOT NULL) OR "
            "status <> 'COMPLETED'",
            name="ck_veterinary_visit_completion",
        ),
        sa.CheckConstraint(
            "(status = 'CANCELLED' AND cancellation_reason IS NOT NULL) OR "
            "status <> 'CANCELLED'",
            name="ck_veterinary_visit_cancellation",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_veterinary_visit_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id", "veterinarian_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_veterinary_visit_member",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_veterinary_visit_scope"
        ),
    )
    op.create_index(
        "ix_veterinary_visit_schedule",
        "veterinary_visits",
        ["farm_id", "status", "planned_at"],
    )
    op.create_index(
        "ix_veterinary_visit_history",
        "veterinary_visits",
        ["farm_id", "cattle_id", "requested_at"],
    )

    op.create_table(
        "health_record_corrections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("record_type", sa.String(50), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("correction_note", sa.Text(), nullable=False),
        sa.Column("previous_data", postgresql.JSONB(), nullable=True),
        sa.Column("replacement_data", postgresql.JSONB(), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(btrim(reason)) >= 3", name="ck_health_correction_reason"
        ),
        sa.CheckConstraint(
            "length(btrim(correction_note)) >= 3",
            name="ck_health_correction_note",
        ),
        sa.CheckConstraint(
            "record_type IN ('ENCOUNTER', 'DIAGNOSIS', "
            "'VACCINATION_SCHEDULE', 'VACCINATION_ADMINISTRATION', "
            "'TREATMENT', 'MEDICATION_ADMINISTRATION', "
            "'VETERINARY_VISIT')",
            name="ck_health_correction_record_type",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_health_correction_cattle_farm",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_health_correction_record",
        "health_record_corrections",
        ["farm_id", "record_type", "record_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_health_correction_record", table_name="health_record_corrections"
    )
    op.drop_table("health_record_corrections")
    op.drop_index(
        "ix_veterinary_visit_history", table_name="veterinary_visits"
    )
    op.drop_index(
        "ix_veterinary_visit_schedule", table_name="veterinary_visits"
    )
    op.drop_table("veterinary_visits")
    op.drop_index(
        "ix_medication_administration_history",
        table_name="medication_administrations",
    )
    op.drop_table("medication_administrations")
    op.drop_index("ix_treatment_plan_farm_status", table_name="treatment_plans")
    op.drop_index("ix_treatment_plan_history", table_name="treatment_plans")
    op.drop_table("treatment_plans")
    op.drop_index(
        "ix_vaccination_administration_history",
        table_name="vaccination_administrations",
    )
    op.drop_index(
        "uq_vaccination_administration_event",
        table_name="vaccination_administrations",
    )
    op.drop_table("vaccination_administrations")
    op.drop_index(
        "uq_vaccination_schedule_active_item",
        table_name="vaccination_schedules",
    )
    op.drop_index(
        "ix_vaccination_schedule_due", table_name="vaccination_schedules"
    )
    op.drop_table("vaccination_schedules")
    op.drop_index(
        "ix_health_diagnosis_encounter", table_name="health_diagnoses"
    )
    op.drop_index(
        "ix_health_diagnosis_history", table_name="health_diagnoses"
    )
    op.drop_table("health_diagnoses")
    op.drop_index(
        "ix_health_encounter_farm_status", table_name="health_encounters"
    )
    op.drop_index(
        "ix_health_encounter_history", table_name="health_encounters"
    )
    op.drop_table("health_encounters")

    op.execute(
        sa.text(
            "DELETE FROM permissions "
            "WHERE code = ANY(CAST(:codes AS text[]))"
        ).bindparams(codes=HEALTH_PERMISSIONS)
    )
    for enum_type in reversed(
        (
            encounter_type,
            encounter_status,
            diagnosis_severity,
            diagnosis_status,
            schedule_status,
            treatment_status,
            visit_status,
        )
    ):
        enum_type.drop(op.get_bind(), checkfirst=True)
