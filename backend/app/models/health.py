import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EncounterType(str, enum.Enum):
    ROUTINE = "ROUTINE"
    ILLNESS = "ILLNESS"
    INJURY = "INJURY"
    EMERGENCY = "EMERGENCY"
    FOLLOW_UP = "FOLLOW_UP"


class EncounterStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"


class DiagnosisSeverity(str, enum.Enum):
    MILD = "MILD"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class DiagnosisStatus(str, enum.Enum):
    SUSPECTED = "SUSPECTED"
    CONFIRMED = "CONFIRMED"
    RULED_OUT = "RULED_OUT"
    RESOLVED = "RESOLVED"


class VaccinationScheduleStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TreatmentStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    STOPPED = "STOPPED"
    CANCELLED = "CANCELLED"


class VeterinaryVisitStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class HealthEncounter(Base):
    __tablename__ = "health_encounters"
    __table_args__ = (
        UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_health_encounter_scope"
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_health_encounter_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["farm_id", "responsible_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_health_encounter_responsible_member",
        ),
        CheckConstraint(
            "(status = 'FINALIZED' AND finalized_at IS NOT NULL) OR "
            "(status = 'DRAFT' AND finalized_at IS NULL)",
            name="ck_health_encounter_finalization",
        ),
        CheckConstraint(
            "follow_up_due_at IS NULL OR follow_up_due_at >= occurred_at",
            name="ck_health_encounter_follow_up_after_event",
        ),
        Index(
            "ix_health_encounter_history",
            "farm_id",
            "cattle_id",
            "occurred_at",
        ),
        Index("ix_health_encounter_farm_status", "farm_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    encounter_type: Mapped[EncounterType] = mapped_column(
        Enum(EncounterType, name="health_encounter_type"), nullable=False
    )
    status: Mapped[EncounterStatus] = mapped_column(
        Enum(EncounterStatus, name="health_encounter_status"),
        default=EncounterStatus.DRAFT,
        server_default=EncounterStatus.DRAFT.value,
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    symptoms: Mapped[str | None] = mapped_column(Text)
    clinical_observations: Mapped[str | None] = mapped_column(Text)
    professional_name: Mapped[str | None] = mapped_column(String(200))
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    follow_up_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    follow_up_notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )


class HealthDiagnosis(Base):
    __tablename__ = "health_diagnoses"
    __table_args__ = (
        UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_health_diagnosis_scope"
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_health_diagnosis_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["encounter_id", "farm_id", "cattle_id"],
            [
                "health_encounters.id",
                "health_encounters.farm_id",
                "health_encounters.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_health_diagnosis_encounter_scope",
        ),
        ForeignKeyConstraint(
            ["farm_id", "responsible_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_health_diagnosis_responsible_member",
        ),
        CheckConstraint(
            "length(btrim(condition_name)) > 0",
            name="ck_health_diagnosis_condition_not_empty",
        ),
        Index(
            "ix_health_diagnosis_history",
            "farm_id",
            "cattle_id",
            "diagnosed_at",
        ),
        Index("ix_health_diagnosis_encounter", "encounter_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    condition_name: Mapped[str] = mapped_column(String(200), nullable=False)
    standardized_code: Mapped[str | None] = mapped_column(String(50))
    clinical_signs: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[DiagnosisSeverity] = mapped_column(
        Enum(DiagnosisSeverity, name="health_diagnosis_severity"),
        nullable=False,
    )
    status: Mapped[DiagnosisStatus] = mapped_column(
        Enum(DiagnosisStatus, name="health_diagnosis_status"),
        nullable=False,
    )
    diagnosed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    follow_up_recommendations: Mapped[str | None] = mapped_column(Text)
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VaccinationSchedule(Base):
    __tablename__ = "vaccination_schedules"
    __table_args__ = (
        UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_vaccination_schedule_scope"
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_schedule_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["farm_id", "responsible_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_schedule_responsible_member",
        ),
        CheckConstraint(
            "due_date >= scheduled_date",
            name="ck_vaccination_schedule_due_date",
        ),
        CheckConstraint(
            "(status = 'CANCELLED' AND cancelled_at IS NOT NULL AND "
            "cancellation_reason IS NOT NULL) OR "
            "(status <> 'CANCELLED' AND cancelled_at IS NULL)",
            name="ck_vaccination_schedule_cancellation",
        ),
        CheckConstraint(
            "(status = 'COMPLETED' AND completed_at IS NOT NULL) OR "
            "(status <> 'COMPLETED' AND completed_at IS NULL)",
            name="ck_vaccination_schedule_completion",
        ),
        Index(
            "ix_vaccination_schedule_due",
            "farm_id",
            "status",
            "due_date",
        ),
        Index(
            "uq_vaccination_schedule_active_item",
            "farm_id",
            "cattle_id",
            text("lower(btrim(vaccine_name))"),
            "scheduled_date",
            unique=True,
            postgresql_where=text("status = 'SCHEDULED'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    vaccine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[VaccinationScheduleStatus] = mapped_column(
        Enum(
            VaccinationScheduleStatus,
            name="vaccination_schedule_status",
        ),
        default=VaccinationScheduleStatus.SCHEDULED,
        server_default=VaccinationScheduleStatus.SCHEDULED.value,
        nullable=False,
    )
    responsible_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))


class VaccinationAdministration(Base):
    __tablename__ = "vaccination_administrations"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "farm_id",
            "cattle_id",
            name="uq_vaccination_administration_scope",
        ),
        UniqueConstraint(
            "schedule_id", name="uq_vaccination_administration_schedule"
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_administration_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["schedule_id", "farm_id", "cattle_id"],
            [
                "vaccination_schedules.id",
                "vaccination_schedules.farm_id",
                "vaccination_schedules.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_vaccination_administration_schedule_scope",
        ),
        ForeignKeyConstraint(
            ["farm_id", "administered_by_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_vaccination_administration_member",
        ),
        CheckConstraint("dose > 0", name="ck_vaccination_dose_positive"),
        CheckConstraint(
            "expiry_date IS NULL OR expiry_date >= administered_at::date",
            name="ck_vaccination_not_expired_at_administration",
        ),
        CheckConstraint(
            "follow_up_due_at IS NULL OR follow_up_due_at >= administered_at",
            name="ck_vaccination_follow_up_after_administration",
        ),
        Index(
            "ix_vaccination_administration_history",
            "farm_id",
            "cattle_id",
            "administered_at",
        ),
        Index(
            "uq_vaccination_administration_event",
            "farm_id",
            "cattle_id",
            text("lower(btrim(vaccine_name))"),
            "administered_at",
            text("coalesce(batch_lot_number, '')"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    vaccine_name: Mapped[str] = mapped_column(String(200), nullable=False)
    administered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dose: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    dose_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    route: Mapped[str | None] = mapped_column(String(50))
    batch_lot_number: Mapped[str | None] = mapped_column(String(100))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    administered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    follow_up_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    next_due_date: Mapped[date | None] = mapped_column(Date)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"
    __table_args__ = (
        UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_treatment_plan_scope"
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_treatment_plan_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["encounter_id", "farm_id", "cattle_id"],
            [
                "health_encounters.id",
                "health_encounters.farm_id",
                "health_encounters.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_treatment_plan_encounter_scope",
        ),
        ForeignKeyConstraint(
            ["diagnosis_id", "farm_id", "cattle_id"],
            [
                "health_diagnoses.id",
                "health_diagnoses.farm_id",
                "health_diagnoses.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_treatment_plan_diagnosis_scope",
        ),
        ForeignKeyConstraint(
            ["farm_id", "prescribed_by_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_treatment_plan_prescriber_member",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_treatment_plan_date_range",
        ),
        CheckConstraint(
            "dosage_quantity IS NULL OR dosage_quantity > 0",
            name="ck_treatment_plan_dosage_positive",
        ),
        CheckConstraint(
            "(dosage_quantity IS NULL) = (dosage_unit IS NULL)",
            name="ck_treatment_plan_dosage_complete",
        ),
        CheckConstraint(
            "withdrawal_period_days IS NULL OR withdrawal_period_days >= 0",
            name="ck_treatment_plan_withdrawal_nonnegative",
        ),
        Index(
            "ix_treatment_plan_history",
            "farm_id",
            "cattle_id",
            "start_date",
        ),
        Index("ix_treatment_plan_farm_status", "farm_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    diagnosis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    medication_name: Mapped[str | None] = mapped_column(String(200))
    dosage_quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    dosage_unit: Mapped[str | None] = mapped_column(String(30))
    administration_frequency: Mapped[str | None] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[TreatmentStatus] = mapped_column(
        Enum(TreatmentStatus, name="health_treatment_status"),
        default=TreatmentStatus.PLANNED,
        server_default=TreatmentStatus.PLANNED.value,
        nullable=False,
    )
    prescribed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    withdrawal_period_days: Mapped[int | None]
    withdrawal_notes: Mapped[str | None] = mapped_column(String(500))
    follow_up_notes: Mapped[str | None] = mapped_column(Text)
    status_reason: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class MedicationAdministration(Base):
    __tablename__ = "medication_administrations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_medication_administration_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["treatment_id", "farm_id", "cattle_id"],
            [
                "treatment_plans.id",
                "treatment_plans.farm_id",
                "treatment_plans.cattle_id",
            ],
            ondelete="RESTRICT",
            name="fk_medication_administration_treatment_scope",
        ),
        ForeignKeyConstraint(
            ["farm_id", "administered_by_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_medication_administration_member",
        ),
        UniqueConstraint(
            "treatment_id",
            "administered_at",
            name="uq_medication_administration_event",
        ),
        CheckConstraint(
            "quantity > 0", name="ck_medication_administration_quantity"
        ),
        Index(
            "ix_medication_administration_history",
            "farm_id",
            "cattle_id",
            "administered_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    treatment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    medication_name: Mapped[str] = mapped_column(String(200), nullable=False)
    administered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    route: Mapped[str | None] = mapped_column(String(50))
    administered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VeterinaryVisit(Base):
    __tablename__ = "veterinary_visits"
    __table_args__ = (
        UniqueConstraint(
            "id", "farm_id", "cattle_id", name="uq_veterinary_visit_scope"
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_veterinary_visit_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["farm_id", "veterinarian_user_id"],
            ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT",
            name="fk_veterinary_visit_member",
        ),
        CheckConstraint(
            "actual_at IS NULL OR actual_at >= requested_at",
            name="ck_veterinary_visit_actual_after_request",
        ),
        CheckConstraint(
            "follow_up_due_at IS NULL OR "
            "(actual_at IS NOT NULL AND follow_up_due_at >= actual_at)",
            name="ck_veterinary_visit_follow_up",
        ),
        CheckConstraint(
            "(status = 'COMPLETED' AND actual_at IS NOT NULL) OR "
            "status <> 'COMPLETED'",
            name="ck_veterinary_visit_completion",
        ),
        CheckConstraint(
            "(status = 'CANCELLED' AND cancellation_reason IS NOT NULL) OR "
            "status <> 'CANCELLED'",
            name="ck_veterinary_visit_cancellation",
        ),
        Index(
            "ix_veterinary_visit_schedule",
            "farm_id",
            "status",
            "planned_at",
        ),
        Index(
            "ix_veterinary_visit_history",
            "farm_id",
            "cattle_id",
            "requested_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    status: Mapped[VeterinaryVisitStatus] = mapped_column(
        Enum(VeterinaryVisitStatus, name="veterinary_visit_status"),
        default=VeterinaryVisitStatus.REQUESTED,
        server_default=VeterinaryVisitStatus.REQUESTED.value,
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actual_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    veterinarian_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True)
    )
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    follow_up_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    follow_up_notes: Mapped[str | None] = mapped_column(Text)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class HealthRecordCorrection(Base):
    __tablename__ = "health_record_corrections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_health_correction_cattle_farm",
        ),
        CheckConstraint(
            "length(btrim(reason)) >= 3",
            name="ck_health_correction_reason",
        ),
        CheckConstraint(
            "length(btrim(correction_note)) >= 3",
            name="ck_health_correction_note",
        ),
        CheckConstraint(
            "record_type IN ('ENCOUNTER', 'DIAGNOSIS', "
            "'VACCINATION_SCHEDULE', 'VACCINATION_ADMINISTRATION', "
            "'TREATMENT', 'MEDICATION_ADMINISTRATION', "
            "'VETERINARY_VISIT')",
            name="ck_health_correction_record_type",
        ),
        Index(
            "ix_health_correction_record",
            "farm_id",
            "record_type",
            "record_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    record_type: Mapped[str] = mapped_column(String(50), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    correction_note: Mapped[str] = mapped_column(Text, nullable=False)
    previous_data: Mapped[dict | None] = mapped_column(JSONB)
    replacement_data: Mapped[dict | None] = mapped_column(JSONB)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
