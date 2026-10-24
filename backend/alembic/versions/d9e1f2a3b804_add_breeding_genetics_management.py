"""Add farm-scoped breeding and genetics management.

Revision ID: d9e1f2a3b804
Revises: c8d0e1f2a703
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d9e1f2a3b804"
down_revision = "c8d0e1f2a703"
branch_labels = None
depends_on = None

PERMISSIONS = ["breeding.heat.record", "breeding.event.record", "breeding.pregnancy.assess", "breeding.calving.record", "breeding.pedigree.manage", "breeding.reports.view"]
ENUMS = {
    "heat_intensity": ["LOW", "MODERATE", "HIGH"],
    "breeding_method": ["ARTIFICIAL_INSEMINATION", "NATURAL_MATING"],
    "breeding_event_status": ["PLANNED", "COMPLETED", "CANCELLED", "FOLLOW_UP_REQUIRED"],
    "pregnancy_assessment": ["PREGNANT", "NOT_PREGNANT", "INCONCLUSIVE"],
    "pregnancy_loss_type": ["SUSPECTED", "CONFIRMED"],
    "calving_outcome": ["LIVE_BIRTH", "STILLBIRTH", "MIXED", "UNKNOWN"],
    "delivery_type": ["NORMAL", "ASSISTED", "UNKNOWN"],
    "parent_role": ["DAM", "SIRE"],
    "parentage_status": ["REPORTED", "DOCUMENT_VERIFIED", "DNA_VERIFIED", "DISPUTED"],
    "breeding_reminder_type": ["ESTIMATED_HEAT", "BREEDING_FOLLOW_UP", "PREGNANCY_EXAM", "EXPECTED_CALVING", "POST_CALVING_FOLLOW_UP"],
    "breeding_reminder_status": ["OPEN", "COMPLETED", "CANCELLED"],
    "breeding_audit_action": ["CREATED", "STATUS_CHANGED", "CORRECTED", "CLINICAL_ASSESSMENT", "OFFSPRING_REGISTERED", "PARENTAGE_CHANGED"],
}


def E(name):
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade():
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)
    op.execute(sa.text("INSERT INTO permissions (code) SELECT code FROM unnest(CAST(:codes AS text[])) code ON CONFLICT (code) DO NOTHING").bindparams(codes=PERMISSIONS))

    op.create_table("heat_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("cattle_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False), sa.Column("signs", sa.Text(), nullable=False), sa.Column("intensity", E("heat_intensity")), sa.Column("notes", sa.Text()), sa.Column("estimated_next_heat_at", sa.DateTime(timezone=True)), sa.Column("cycle_length_days", sa.Integer(), server_default="21", nullable=False),
        sa.Column("observed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_heat_cattle_scope"), sa.UniqueConstraint("farm_id", "client_request_id", name="uq_heat_request"), sa.UniqueConstraint("id", "farm_id", name="uq_heat_scope"))
    op.create_index("ix_heat_history", "heat_observations", ["farm_id", "cattle_id", "observed_at"])

    op.create_table("breeding_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("cow_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("sire_id", postgresql.UUID(as_uuid=True)), sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", E("breeding_method"), nullable=False), sa.Column("status", E("breeding_event_status"), nullable=False), sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("semen_reference", sa.String(150)), sa.Column("technician_name", sa.String(200)), sa.Column("follow_up_due_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.Text()),
        sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cow_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_breeding_cow_scope"), sa.ForeignKeyConstraint(["sire_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_breeding_sire_scope"),
        sa.UniqueConstraint("farm_id", "client_request_id", name="uq_breeding_event_request"), sa.UniqueConstraint("id", "farm_id", name="uq_breeding_event_scope"), sa.CheckConstraint("sire_id IS NULL OR sire_id <> cow_id", name="ck_breeding_distinct_parents"), sa.CheckConstraint("method <> 'NATURAL_MATING' OR sire_id IS NOT NULL", name="ck_natural_mating_sire"))
    op.create_index("ix_breeding_event_history", "breeding_events", ["farm_id", "cow_id", "scheduled_at"])

    op.create_table("pregnancy_examinations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("cattle_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("breeding_event_id", postgresql.UUID(as_uuid=True)), sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("examined_at", sa.DateTime(timezone=True), nullable=False), sa.Column("assessment", E("pregnancy_assessment"), nullable=False), sa.Column("clinical_assessment", sa.Text(), nullable=False), sa.Column("expected_calving_date", sa.Date()), sa.Column("gestation_days_used", sa.Integer()), sa.Column("follow_up_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.Text()),
        sa.Column("examined_by_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("supersedes_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pregnancy_examinations.id", ondelete="RESTRICT")), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_exam_cattle_scope"), sa.ForeignKeyConstraint(["breeding_event_id", "farm_id"], ["breeding_events.id", "breeding_events.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_exam_event_scope"), sa.ForeignKeyConstraint(["farm_id", "examined_by_id"], ["farm_members.farm_id", "farm_members.user_id"], ondelete="RESTRICT", name="fk_pregnancy_exam_vet_member"),
        sa.UniqueConstraint("farm_id", "client_request_id", name="uq_pregnancy_exam_request"), sa.UniqueConstraint("id", "farm_id", name="uq_pregnancy_exam_scope"), sa.CheckConstraint("expected_calving_date IS NULL OR assessment = 'PREGNANT'", name="ck_exam_calving_requires_pregnant"))
    op.create_index("ix_pregnancy_exam_history", "pregnancy_examinations", ["farm_id", "cattle_id", "examined_at"])

    op.create_table("pregnancy_losses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("cattle_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("pregnancy_examination_id", postgresql.UUID(as_uuid=True)), sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False), sa.Column("loss_type", E("pregnancy_loss_type"), nullable=False), sa.Column("clinical_assessment", sa.Text(), nullable=False), sa.Column("follow_up_at", sa.DateTime(timezone=True)), sa.Column("assessed_by_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_loss_cattle_scope"), sa.ForeignKeyConstraint(["pregnancy_examination_id", "farm_id"], ["pregnancy_examinations.id", "pregnancy_examinations.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_loss_exam_scope"), sa.ForeignKeyConstraint(["farm_id", "assessed_by_id"], ["farm_members.farm_id", "farm_members.user_id"], ondelete="RESTRICT", name="fk_pregnancy_loss_vet_member"), sa.UniqueConstraint("farm_id", "client_request_id", name="uq_pregnancy_loss_request"))
    op.create_index("ix_pregnancy_loss_history", "pregnancy_losses", ["farm_id", "cattle_id", "occurred_on"])

    op.create_table("calving_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("dam_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("breeding_event_id", postgresql.UUID(as_uuid=True)), sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("calved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", E("calving_outcome"), nullable=False), sa.Column("delivery_type", E("delivery_type"), nullable=False), sa.Column("calf_count", sa.Integer(), nullable=False), sa.Column("live_count", sa.Integer(), nullable=False), sa.Column("stillborn_count", sa.Integer(), nullable=False), sa.Column("factual_observations", sa.Text()), sa.Column("assistance_details", sa.Text()), sa.Column("clinical_complications", sa.Text()), sa.Column("clinical_diagnosis", sa.Text()), sa.Column("clinical_recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("post_calving_follow_up_at", sa.DateTime(timezone=True)), sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dam_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_calving_dam_scope"), sa.ForeignKeyConstraint(["breeding_event_id", "farm_id"], ["breeding_events.id", "breeding_events.farm_id"], ondelete="RESTRICT", name="fk_calving_breeding_scope"), sa.UniqueConstraint("farm_id", "client_request_id", name="uq_calving_request"), sa.UniqueConstraint("id", "farm_id", name="uq_calving_scope"), sa.CheckConstraint("calf_count > 0", name="ck_calving_count_positive"), sa.CheckConstraint("live_count >= 0 AND stillborn_count >= 0 AND live_count + stillborn_count <= calf_count", name="ck_calving_counts_valid"))
    op.create_index("ix_calving_history", "calving_events", ["farm_id", "dam_id", "calved_at"])

    op.create_table("calving_offspring",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("calving_event_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("cattle_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("birth_order", sa.Integer(), nullable=False), sa.Column("birth_weight_kg", sa.Numeric(7,2)), sa.Column("registered_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["calving_event_id", "farm_id"], ["calving_events.id", "calving_events.farm_id"], ondelete="RESTRICT", name="fk_offspring_calving_scope"), sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_offspring_cattle_scope"), sa.UniqueConstraint("calving_event_id", "birth_order", name="uq_offspring_birth_order"), sa.UniqueConstraint("farm_id", "cattle_id", name="uq_offspring_cattle"))

    op.create_table("parentage_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("child_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("parent_role", E("parent_role"), nullable=False), sa.Column("status", E("parentage_status"), nullable=False), sa.Column("confidence_percent", sa.Numeric(5,2)), sa.Column("evidence_reference", sa.String(500)), sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("recorded_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["child_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_parentage_child_scope"), sa.ForeignKeyConstraint(["parent_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_parentage_parent_scope"), sa.UniqueConstraint("farm_id", "client_request_id", name="uq_parentage_request"), sa.CheckConstraint("child_id <> parent_id", name="ck_parentage_not_self"))
    op.create_index("ix_parentage_history", "parentage_verifications", ["farm_id", "child_id", "created_at"])

    op.create_table("breeding_reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("cattle_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("client_request_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("reminder_type", E("breeding_reminder_type"), nullable=False), sa.Column("due_at", sa.DateTime(timezone=True), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("notes", sa.Text()), sa.Column("assigned_to_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT")), sa.Column("status", E("breeding_reminder_status"), server_default="OPEN", nullable=False), sa.Column("is_estimate", sa.Boolean(), server_default="false", nullable=False), sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_breeding_reminder_cattle_scope"), sa.UniqueConstraint("farm_id", "client_request_id", name="uq_breeding_reminder_request"))
    op.create_index("ix_breeding_reminder_due", "breeding_reminders", ["farm_id", "status", "due_at"])

    op.create_table("breeding_audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("farm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False), sa.Column("entity_type", sa.String(50), nullable=False), sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False), sa.Column("action", E("breeding_audit_action"), nullable=False), sa.Column("summary", sa.Text(), nullable=False), sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_breeding_audit_entity", "breeding_audit_events", ["farm_id", "entity_type", "entity_id", "created_at"])


def downgrade():
    for table, indexes in [
        ("breeding_audit_events", ["ix_breeding_audit_entity"]), ("breeding_reminders", ["ix_breeding_reminder_due"]), ("parentage_verifications", ["ix_parentage_history"]), ("calving_offspring", []), ("calving_events", ["ix_calving_history"]), ("pregnancy_losses", ["ix_pregnancy_loss_history"]), ("pregnancy_examinations", ["ix_pregnancy_exam_history"]), ("breeding_events", ["ix_breeding_event_history"]), ("heat_observations", ["ix_heat_history"]),
    ]:
        for index in indexes: op.drop_index(index, table_name=table)
        op.drop_table(table)
    op.execute(sa.text("DELETE FROM farm_role_permissions WHERE permission_code = ANY(:codes)").bindparams(codes=PERMISSIONS))
    op.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)").bindparams(codes=PERMISSIONS))
    bind = op.get_bind()
    for name, values in reversed(list(ENUMS.items())):
        postgresql.ENUM(*values, name=name).drop(bind, checkfirst=True)
