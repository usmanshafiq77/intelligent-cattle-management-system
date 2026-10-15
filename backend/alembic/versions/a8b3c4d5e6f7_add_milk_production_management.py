"""Add milk production, lactation, quality, and correction management.

Revision ID: a8b3c4d5e6f7
Revises: f7a2b3c4d5e6

The upgrade is additive and does not alter existing business records.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a8b3c4d5e6f7"
down_revision = "f7a2b3c4d5e6"
branch_labels = None
depends_on = None

MILK_PERMISSIONS = [
    "milk.lactation.manage",
    "milk.quality.manage",
    "milk.correct",
    "milk.analytics.view",
    "milk.bulk.create",
]

lactation_status = postgresql.ENUM(
    "ACTIVE", "DRY", "COMPLETED", name="milk_lactation_status", create_type=False
)
session_kind = postgresql.ENUM(
    "MORNING", "EVENING", "ADDITIONAL", name="milking_session_kind", create_type=False
)
correction_target = postgresql.ENUM(
    "SESSION", "QUALITY", name="milk_correction_target", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (lactation_status, session_kind, correction_target):
        enum_type.create(bind, checkfirst=True)

    op.execute(sa.text(
        "INSERT INTO permissions (code) "
        "SELECT code FROM unnest(CAST(:codes AS text[])) AS code "
        "ON CONFLICT (code) DO NOTHING"
    ).bindparams(codes=MILK_PERMISSIONS))

    op.create_table(
        "milk_lactations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("dry_off_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", lactation_status, server_default="ACTIVE", nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sequence_number > 0", name="ck_milk_lactation_sequence_positive"),
        sa.CheckConstraint("dry_off_date IS NULL OR dry_off_date >= start_date", name="ck_milk_lactation_dry_after_start"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_milk_lactation_end_after_start"),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND dry_off_date IS NULL AND end_date IS NULL) OR "
            "(status = 'DRY' AND dry_off_date IS NOT NULL AND end_date IS NULL) OR "
            "(status = 'COMPLETED' AND end_date IS NOT NULL)",
            name="ck_milk_lactation_status_dates",
        ),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_milk_lactation_cattle_farm"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "farm_id", "cattle_id", name="uq_milk_lactation_scope"),
        sa.UniqueConstraint("farm_id", "cattle_id", "sequence_number", name="uq_milk_lactation_sequence"),
    )
    op.create_index("uq_milk_lactation_one_active", "milk_lactations", ["farm_id", "cattle_id"], unique=True, postgresql_where=sa.text("status = 'ACTIVE'"))
    op.create_index("ix_milk_lactation_history", "milk_lactations", ["farm_id", "cattle_id", "start_date"])

    op.create_table(
        "milking_sessions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("lactation_id", sa.UUID(), nullable=False),
        sa.Column("milking_date", sa.Date(), nullable=False),
        sa.Column("session_kind", session_kind, nullable=False),
        sa.Column("session_code", sa.String(50), nullable=False),
        sa.Column("recorded_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("volume_liters", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit", sa.String(3), server_default="L", nullable=False),
        sa.Column("operator_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_id", sa.UUID(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("volume_liters >= 0", name="ck_milking_session_volume_nonnegative"),
        sa.CheckConstraint("length(btrim(session_code)) > 0", name="ck_milking_session_code_not_empty"),
        sa.CheckConstraint("unit = 'L'", name="ck_milking_session_canonical_unit"),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_milking_session_cattle_farm"),
        sa.ForeignKeyConstraint(["lactation_id", "farm_id", "cattle_id"], ["milk_lactations.id", "milk_lactations.farm_id", "milk_lactations.cattle_id"], ondelete="RESTRICT", name="fk_milking_session_lactation_scope"),
        sa.ForeignKeyConstraint(["farm_id", "operator_id"], ["farm_members.farm_id", "farm_members.user_id"], ondelete="RESTRICT", name="fk_milking_session_operator_member"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "farm_id", "cattle_id", name="uq_milking_session_scope"),
        sa.UniqueConstraint("farm_id", "cattle_id", "milking_date", "session_code", name="uq_milking_session_identity"),
    )
    op.create_index("ix_milking_session_history", "milking_sessions", ["farm_id", "cattle_id", "milking_date"])
    op.create_index("ix_milking_session_lactation", "milking_sessions", ["lactation_id", "milking_date"])
    op.create_index("ix_milking_session_farm_date", "milking_sessions", ["farm_id", "milking_date"])

    op.create_table(
        "milk_quality_measurements",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("fat_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("snf_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("protein_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("density", sa.Numeric(8, 4), nullable=True),
        sa.Column("temperature_celsius", sa.Numeric(6, 2), nullable=True),
        sa.Column("somatic_cell_count", sa.BigInteger(), nullable=True),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("fat_percent IS NULL OR (fat_percent >= 0 AND fat_percent <= 100)", name="ck_milk_quality_fat_range"),
        sa.CheckConstraint("snf_percent IS NULL OR (snf_percent >= 0 AND snf_percent <= 100)", name="ck_milk_quality_snf_range"),
        sa.CheckConstraint("protein_percent IS NULL OR (protein_percent >= 0 AND protein_percent <= 100)", name="ck_milk_quality_protein_range"),
        sa.CheckConstraint("density IS NULL OR density > 0", name="ck_milk_quality_density_positive"),
        sa.CheckConstraint("temperature_celsius IS NULL OR temperature_celsius >= -273.15", name="ck_milk_quality_temperature_physical"),
        sa.CheckConstraint("somatic_cell_count IS NULL OR somatic_cell_count >= 0", name="ck_milk_quality_scc_nonnegative"),
        sa.CheckConstraint("num_nonnulls(fat_percent, snf_percent, protein_percent, density, temperature_celsius, somatic_cell_count) > 0", name="ck_milk_quality_has_measurement"),
        sa.ForeignKeyConstraint(["session_id", "farm_id", "cattle_id"], ["milking_sessions.id", "milking_sessions.farm_id", "milking_sessions.cattle_id"], ondelete="RESTRICT", name="fk_milk_quality_session_scope"),
        sa.ForeignKeyConstraint(["recorded_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "farm_id", "cattle_id", name="uq_milk_quality_scope"),
        sa.UniqueConstraint("session_id", "tested_at", name="uq_milk_quality_sample"),
    )
    op.create_index("ix_milk_quality_history", "milk_quality_measurements", ["farm_id", "cattle_id", "tested_at"])
    op.create_index("ix_milk_quality_session", "milk_quality_measurements", ["session_id"])

    op.create_table(
        "milk_record_corrections",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("target_type", correction_target, nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("original_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("replacement_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("corrected_by_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(btrim(reason)) >= 3", name="ck_milk_correction_reason"),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_milk_correction_cattle_farm"),
        sa.ForeignKeyConstraint(["corrected_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_milk_correction_target", "milk_record_corrections", ["farm_id", "target_type", "target_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_milk_correction_target", table_name="milk_record_corrections")
    op.drop_table("milk_record_corrections")
    op.drop_index("ix_milk_quality_session", table_name="milk_quality_measurements")
    op.drop_index("ix_milk_quality_history", table_name="milk_quality_measurements")
    op.drop_table("milk_quality_measurements")
    op.drop_index("ix_milking_session_farm_date", table_name="milking_sessions")
    op.drop_index("ix_milking_session_lactation", table_name="milking_sessions")
    op.drop_index("ix_milking_session_history", table_name="milking_sessions")
    op.drop_table("milking_sessions")
    op.drop_index("ix_milk_lactation_history", table_name="milk_lactations")
    op.drop_index("uq_milk_lactation_one_active", table_name="milk_lactations")
    op.drop_table("milk_lactations")
    op.execute(sa.text("DELETE FROM farm_role_permissions WHERE permission_code = ANY(:codes)").bindparams(codes=MILK_PERMISSIONS))
    op.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)").bindparams(codes=MILK_PERMISSIONS))
    bind = op.get_bind()
    for enum_type in (correction_target, session_kind, lactation_status):
        enum_type.drop(bind, checkfirst=True)
