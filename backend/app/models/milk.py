import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
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


class LactationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    DRY = "DRY"
    COMPLETED = "COMPLETED"


class MilkingSessionKind(str, enum.Enum):
    MORNING = "MORNING"
    EVENING = "EVENING"
    ADDITIONAL = "ADDITIONAL"


class MilkCorrectionTarget(str, enum.Enum):
    SESSION = "SESSION"
    QUALITY = "QUALITY"


class MilkLactation(Base):
    __tablename__ = "milk_lactations"
    __table_args__ = (
        UniqueConstraint("id", "farm_id", "cattle_id", name="uq_milk_lactation_scope"),
        UniqueConstraint(
            "farm_id", "cattle_id", "sequence_number", name="uq_milk_lactation_sequence"
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_milk_lactation_cattle_farm",
        ),
        CheckConstraint("sequence_number > 0", name="ck_milk_lactation_sequence_positive"),
        CheckConstraint(
            "dry_off_date IS NULL OR dry_off_date >= start_date",
            name="ck_milk_lactation_dry_after_start",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date >= start_date",
            name="ck_milk_lactation_end_after_start",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' AND dry_off_date IS NULL AND end_date IS NULL) OR "
            "(status = 'DRY' AND dry_off_date IS NOT NULL AND end_date IS NULL) OR "
            "(status = 'COMPLETED' AND end_date IS NOT NULL)",
            name="ck_milk_lactation_status_dates",
        ),
        Index(
            "uq_milk_lactation_one_active",
            "farm_id",
            "cattle_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_milk_lactation_history", "farm_id", "cattle_id", "start_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    dry_off_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[LactationStatus] = mapped_column(
        Enum(LactationStatus, name="milk_lactation_status"),
        default=LactationStatus.ACTIVE,
        server_default=LactationStatus.ACTIVE.value,
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MilkingSession(Base):
    __tablename__ = "milking_sessions"
    __table_args__ = (
        UniqueConstraint("id", "farm_id", "cattle_id", name="uq_milking_session_scope"),
        UniqueConstraint(
            "farm_id", "cattle_id", "milking_date", "session_code",
            name="uq_milking_session_identity",
        ),
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT", name="fk_milking_session_cattle_farm",
        ),
        ForeignKeyConstraint(
            ["lactation_id", "farm_id", "cattle_id"],
            ["milk_lactations.id", "milk_lactations.farm_id", "milk_lactations.cattle_id"],
            ondelete="RESTRICT", name="fk_milking_session_lactation_scope",
        ),
        ForeignKeyConstraint(
            ["farm_id", "operator_id"], ["farm_members.farm_id", "farm_members.user_id"],
            ondelete="RESTRICT", name="fk_milking_session_operator_member",
        ),
        CheckConstraint("volume_liters >= 0", name="ck_milking_session_volume_nonnegative"),
        CheckConstraint("length(btrim(session_code)) > 0", name="ck_milking_session_code_not_empty"),
        CheckConstraint("unit = 'L'", name="ck_milking_session_canonical_unit"),
        Index("ix_milking_session_history", "farm_id", "cattle_id", "milking_date"),
        Index("ix_milking_session_lactation", "lactation_id", "milking_date"),
        Index("ix_milking_session_farm_date", "farm_id", "milking_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    lactation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    milking_date: Mapped[date] = mapped_column(Date, nullable=False)
    session_kind: Mapped[MilkingSessionKind] = mapped_column(
        Enum(MilkingSessionKind, name="milking_session_kind"), nullable=False
    )
    session_code: Mapped[str] = mapped_column(String(50), nullable=False)
    recorded_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    volume_liters: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(3), default="L", server_default="L", nullable=False)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MilkQualityMeasurement(Base):
    __tablename__ = "milk_quality_measurements"
    __table_args__ = (
        UniqueConstraint("id", "farm_id", "cattle_id", name="uq_milk_quality_scope"),
        UniqueConstraint("session_id", "tested_at", name="uq_milk_quality_sample"),
        ForeignKeyConstraint(
            ["session_id", "farm_id", "cattle_id"],
            ["milking_sessions.id", "milking_sessions.farm_id", "milking_sessions.cattle_id"],
            ondelete="RESTRICT", name="fk_milk_quality_session_scope",
        ),
        CheckConstraint("fat_percent IS NULL OR (fat_percent >= 0 AND fat_percent <= 100)", name="ck_milk_quality_fat_range"),
        CheckConstraint("snf_percent IS NULL OR (snf_percent >= 0 AND snf_percent <= 100)", name="ck_milk_quality_snf_range"),
        CheckConstraint("protein_percent IS NULL OR (protein_percent >= 0 AND protein_percent <= 100)", name="ck_milk_quality_protein_range"),
        CheckConstraint("density IS NULL OR density > 0", name="ck_milk_quality_density_positive"),
        CheckConstraint("temperature_celsius IS NULL OR temperature_celsius >= -273.15", name="ck_milk_quality_temperature_physical"),
        CheckConstraint("somatic_cell_count IS NULL OR somatic_cell_count >= 0", name="ck_milk_quality_scc_nonnegative"),
        CheckConstraint(
            "num_nonnulls(fat_percent, snf_percent, protein_percent, density, temperature_celsius, somatic_cell_count) > 0",
            name="ck_milk_quality_has_measurement",
        ),
        Index("ix_milk_quality_history", "farm_id", "cattle_id", "tested_at"),
        Index("ix_milk_quality_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    fat_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    snf_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    protein_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    density: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    temperature_celsius: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    somatic_cell_count: Mapped[int | None] = mapped_column(BigInteger)
    tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MilkRecordCorrection(Base):
    __tablename__ = "milk_record_corrections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"], ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT", name="fk_milk_correction_cattle_farm",
        ),
        CheckConstraint("length(btrim(reason)) >= 3", name="ck_milk_correction_reason"),
        Index("ix_milk_correction_target", "farm_id", "target_type", "target_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_type: Mapped[MilkCorrectionTarget] = mapped_column(
        Enum(MilkCorrectionTarget, name="milk_correction_target"), nullable=False
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    original_values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    replacement_values: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    corrected_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
