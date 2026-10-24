import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HeatIntensity(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class BreedingMethod(str, enum.Enum):
    ARTIFICIAL_INSEMINATION = "ARTIFICIAL_INSEMINATION"
    NATURAL_MATING = "NATURAL_MATING"


class BreedingEventStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FOLLOW_UP_REQUIRED = "FOLLOW_UP_REQUIRED"


class PregnancyAssessment(str, enum.Enum):
    PREGNANT = "PREGNANT"
    NOT_PREGNANT = "NOT_PREGNANT"
    INCONCLUSIVE = "INCONCLUSIVE"


class PregnancyLossType(str, enum.Enum):
    SUSPECTED = "SUSPECTED"
    CONFIRMED = "CONFIRMED"


class CalvingOutcome(str, enum.Enum):
    LIVE_BIRTH = "LIVE_BIRTH"
    STILLBIRTH = "STILLBIRTH"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class DeliveryType(str, enum.Enum):
    NORMAL = "NORMAL"
    ASSISTED = "ASSISTED"
    UNKNOWN = "UNKNOWN"


class ParentRole(str, enum.Enum):
    DAM = "DAM"
    SIRE = "SIRE"


class ParentageStatus(str, enum.Enum):
    REPORTED = "REPORTED"
    DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED"
    DNA_VERIFIED = "DNA_VERIFIED"
    DISPUTED = "DISPUTED"


class ReminderType(str, enum.Enum):
    ESTIMATED_HEAT = "ESTIMATED_HEAT"
    BREEDING_FOLLOW_UP = "BREEDING_FOLLOW_UP"
    PREGNANCY_EXAM = "PREGNANCY_EXAM"
    EXPECTED_CALVING = "EXPECTED_CALVING"
    POST_CALVING_FOLLOW_UP = "POST_CALVING_FOLLOW_UP"


class ReminderStatus(str, enum.Enum):
    OPEN = "OPEN"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BreedingAuditAction(str, enum.Enum):
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    CORRECTED = "CORRECTED"
    CLINICAL_ASSESSMENT = "CLINICAL_ASSESSMENT"
    OFFSPRING_REGISTERED = "OFFSPRING_REGISTERED"
    PARENTAGE_CHANGED = "PARENTAGE_CHANGED"


class HeatObservation(Base):
    __tablename__ = "heat_observations"
    __table_args__ = (
        ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_heat_cattle_scope"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_heat_request"),
        UniqueConstraint("id", "farm_id", name="uq_heat_scope"),
        Index("ix_heat_history", "farm_id", "cattle_id", "observed_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signs: Mapped[str] = mapped_column(Text, nullable=False)
    intensity: Mapped[HeatIntensity | None] = mapped_column(Enum(HeatIntensity, name="heat_intensity"))
    notes: Mapped[str | None] = mapped_column(Text)
    estimated_next_heat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cycle_length_days: Mapped[int] = mapped_column(Integer, default=21, server_default="21", nullable=False)
    observed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BreedingEvent(Base):
    __tablename__ = "breeding_events"
    __table_args__ = (
        ForeignKeyConstraint(["cow_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_breeding_cow_scope"),
        ForeignKeyConstraint(["sire_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_breeding_sire_scope"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_breeding_event_request"),
        UniqueConstraint("id", "farm_id", name="uq_breeding_event_scope"),
        CheckConstraint("sire_id IS NULL OR sire_id <> cow_id", name="ck_breeding_distinct_parents"),
        CheckConstraint("method <> 'NATURAL_MATING' OR sire_id IS NOT NULL", name="ck_natural_mating_sire"),
        Index("ix_breeding_event_history", "farm_id", "cow_id", "scheduled_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sire_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    method: Mapped[BreedingMethod] = mapped_column(Enum(BreedingMethod, name="breeding_method"), nullable=False)
    status: Mapped[BreedingEventStatus] = mapped_column(Enum(BreedingEventStatus, name="breeding_event_status"), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    semen_reference: Mapped[str | None] = mapped_column(String(150))
    technician_name: Mapped[str | None] = mapped_column(String(200))
    follow_up_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PregnancyExamination(Base):
    __tablename__ = "pregnancy_examinations"
    __table_args__ = (
        ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_exam_cattle_scope"),
        ForeignKeyConstraint(["breeding_event_id", "farm_id"], ["breeding_events.id", "breeding_events.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_exam_event_scope"),
        ForeignKeyConstraint(["farm_id", "examined_by_id"], ["farm_members.farm_id", "farm_members.user_id"], ondelete="RESTRICT", name="fk_pregnancy_exam_vet_member"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_pregnancy_exam_request"),
        UniqueConstraint("id", "farm_id", name="uq_pregnancy_exam_scope"),
        CheckConstraint("expected_calving_date IS NULL OR assessment = 'PREGNANT'", name="ck_exam_calving_requires_pregnant"),
        Index("ix_pregnancy_exam_history", "farm_id", "cattle_id", "examined_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    breeding_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    examined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assessment: Mapped[PregnancyAssessment] = mapped_column(Enum(PregnancyAssessment, name="pregnancy_assessment"), nullable=False)
    clinical_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    expected_calving_date: Mapped[date | None] = mapped_column(Date)
    gestation_days_used: Mapped[int | None] = mapped_column(Integer)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    examined_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pregnancy_examinations.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PregnancyLoss(Base):
    __tablename__ = "pregnancy_losses"
    __table_args__ = (
        ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_loss_cattle_scope"),
        ForeignKeyConstraint(["pregnancy_examination_id", "farm_id"], ["pregnancy_examinations.id", "pregnancy_examinations.farm_id"], ondelete="RESTRICT", name="fk_pregnancy_loss_exam_scope"),
        ForeignKeyConstraint(["farm_id", "assessed_by_id"], ["farm_members.farm_id", "farm_members.user_id"], ondelete="RESTRICT", name="fk_pregnancy_loss_vet_member"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_pregnancy_loss_request"),
        Index("ix_pregnancy_loss_history", "farm_id", "cattle_id", "occurred_on"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    pregnancy_examination_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)
    loss_type: Mapped[PregnancyLossType] = mapped_column(Enum(PregnancyLossType, name="pregnancy_loss_type"), nullable=False)
    clinical_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assessed_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CalvingEvent(Base):
    __tablename__ = "calving_events"
    __table_args__ = (
        ForeignKeyConstraint(["dam_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_calving_dam_scope"),
        ForeignKeyConstraint(["breeding_event_id", "farm_id"], ["breeding_events.id", "breeding_events.farm_id"], ondelete="RESTRICT", name="fk_calving_breeding_scope"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_calving_request"),
        UniqueConstraint("id", "farm_id", name="uq_calving_scope"),
        CheckConstraint("calf_count > 0", name="ck_calving_count_positive"),
        CheckConstraint("live_count >= 0 AND stillborn_count >= 0 AND live_count + stillborn_count <= calf_count", name="ck_calving_counts_valid"),
        Index("ix_calving_history", "farm_id", "dam_id", "calved_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    dam_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    breeding_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    calved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome: Mapped[CalvingOutcome] = mapped_column(Enum(CalvingOutcome, name="calving_outcome"), nullable=False)
    delivery_type: Mapped[DeliveryType] = mapped_column(Enum(DeliveryType, name="delivery_type"), nullable=False)
    calf_count: Mapped[int] = mapped_column(Integer, nullable=False)
    live_count: Mapped[int] = mapped_column(Integer, nullable=False)
    stillborn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    factual_observations: Mapped[str | None] = mapped_column(Text)
    assistance_details: Mapped[str | None] = mapped_column(Text)
    clinical_complications: Mapped[str | None] = mapped_column(Text)
    clinical_diagnosis: Mapped[str | None] = mapped_column(Text)
    clinical_recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    post_calving_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CalvingOffspring(Base):
    __tablename__ = "calving_offspring"
    __table_args__ = (
        ForeignKeyConstraint(["calving_event_id", "farm_id"], ["calving_events.id", "calving_events.farm_id"], ondelete="RESTRICT", name="fk_offspring_calving_scope"),
        ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_offspring_cattle_scope"),
        UniqueConstraint("calving_event_id", "birth_order", name="uq_offspring_birth_order"),
        UniqueConstraint("farm_id", "cattle_id", name="uq_offspring_cattle"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    calving_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    birth_order: Mapped[int] = mapped_column(Integer, nullable=False)
    birth_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    registered_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ParentageVerification(Base):
    __tablename__ = "parentage_verifications"
    __table_args__ = (
        ForeignKeyConstraint(["child_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_parentage_child_scope"),
        ForeignKeyConstraint(["parent_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_parentage_parent_scope"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_parentage_request"),
        CheckConstraint("child_id <> parent_id", name="ck_parentage_not_self"),
        Index("ix_parentage_history", "farm_id", "child_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    child_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    parent_role: Mapped[ParentRole] = mapped_column(Enum(ParentRole, name="parent_role"), nullable=False)
    status: Mapped[ParentageStatus] = mapped_column(Enum(ParentageStatus, name="parentage_status"), nullable=False)
    confidence_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    evidence_reference: Mapped[str | None] = mapped_column(String(500))
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BreedingReminder(Base):
    __tablename__ = "breeding_reminders"
    __table_args__ = (
        ForeignKeyConstraint(["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"], ondelete="RESTRICT", name="fk_breeding_reminder_cattle_scope"),
        UniqueConstraint("farm_id", "client_request_id", name="uq_breeding_reminder_request"),
        Index("ix_breeding_reminder_due", "farm_id", "status", "due_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    client_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reminder_type: Mapped[ReminderType] = mapped_column(Enum(ReminderType, name="breeding_reminder_type"), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[ReminderStatus] = mapped_column(Enum(ReminderStatus, name="breeding_reminder_status"), default=ReminderStatus.OPEN, server_default="OPEN", nullable=False)
    is_estimate: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BreedingAuditEvent(Base):
    __tablename__ = "breeding_audit_events"
    __table_args__ = (Index("ix_breeding_audit_entity", "farm_id", "entity_type", "entity_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("farms.id", ondelete="RESTRICT"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[BreedingAuditAction] = mapped_column(Enum(BreedingAuditAction, name="breeding_audit_action"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
