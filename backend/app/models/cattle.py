import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
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
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Species(str, enum.Enum):
    CATTLE = "CATTLE"
    BUFFALO = "BUFFALO"


class AnimalSex(str, enum.Enum):
    FEMALE = "FEMALE"
    MALE = "MALE"


class AnimalCategory(str, enum.Enum):
    CALF = "CALF"
    HEIFER = "HEIFER"
    COW = "COW"
    BULL = "BULL"
    STEER = "STEER"
    OTHER = "OTHER"


class CattleStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SOLD = "SOLD"
    DECEASED = "DECEASED"
    TRANSFERRED = "TRANSFERRED"
    MISSING = "MISSING"
    ARCHIVED = "ARCHIVED"


class AcquisitionMethod(str, enum.Enum):
    BORN_ON_FARM = "BORN_ON_FARM"
    PURCHASED = "PURCHASED"
    TRANSFERRED_IN = "TRANSFERRED_IN"
    DONATED = "DONATED"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class MediaPurpose(str, enum.Enum):
    PROFILE = "PROFILE"
    IDENTIFICATION = "IDENTIFICATION"
    HEALTH = "HEALTH"
    OTHER = "OTHER"


class Breed(Base):
    __tablename__ = "breeds"
    __table_args__ = (
        UniqueConstraint(
            "species", "normalized_name", name="uq_breeds_species_name"
        ),
        UniqueConstraint("id", "species", name="uq_breeds_id_species"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    species: Mapped[Species] = mapped_column(
        Enum(Species, name="cattle_species"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Cattle(Base):
    __tablename__ = "cattle"
    __table_args__ = (
        UniqueConstraint(
            "farm_id", "normalized_tag", name="uq_cattle_farm_tag"
        ),
        UniqueConstraint("id", "farm_id", name="uq_cattle_id_farm"),
        ForeignKeyConstraint(
            ["breed_id", "species"],
            ["breeds.id", "breeds.species"],
            ondelete="RESTRICT",
            name="fk_cattle_breed_species",
        ),
        ForeignKeyConstraint(
            ["mother_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_mother_same_farm",
        ),
        ForeignKeyConstraint(
            ["father_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_father_same_farm",
        ),
        CheckConstraint(
            "category NOT IN ('HEIFER', 'COW') OR sex = 'FEMALE'",
            name="ck_cattle_female_category",
        ),
        CheckConstraint(
            "category NOT IN ('BULL', 'STEER') OR sex = 'MALE'",
            name="ck_cattle_male_category",
        ),
        CheckConstraint(
            "NOT birth_date_estimated OR date_of_birth IS NOT NULL",
            name="ck_cattle_estimated_birth_has_date",
        ),
        CheckConstraint(
            "initial_acquisition_cost IS NULL OR initial_acquisition_cost >= 0",
            name="ck_cattle_acquisition_cost_nonnegative",
        ),
        CheckConstraint(
            "(initial_acquisition_cost IS NULL) = "
            "(initial_acquisition_currency IS NULL)",
            name="ck_cattle_acquisition_money_complete",
        ),
        CheckConstraint(
            "length(btrim(normalized_tag)) > 0",
            name="ck_cattle_normalized_tag_not_empty",
        ),
        CheckConstraint("mother_id IS NULL OR mother_id <> id", name="ck_cattle_mother_not_self"),
        CheckConstraint("father_id IS NULL OR father_id <> id", name="ck_cattle_father_not_self"),
        CheckConstraint(
            "mother_id IS NULL OR father_id IS NULL OR mother_id <> father_id",
            name="ck_cattle_parents_distinct",
        ),
        Index("ix_cattle_farm_status", "farm_id", "status"),
        Index("ix_cattle_farm_species", "farm_id", "species"),
        Index("ix_cattle_farm_breed", "farm_id", "breed_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tag_number: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_tag: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str | None] = mapped_column(String(150))
    species: Mapped[Species] = mapped_column(
        Enum(Species, name="cattle_species", create_type=False),
        nullable=False,
    )
    sex: Mapped[AnimalSex] = mapped_column(
        Enum(AnimalSex, name="cattle_sex"), nullable=False
    )
    category: Mapped[AnimalCategory] = mapped_column(
        Enum(AnimalCategory, name="cattle_category"), nullable=False
    )
    breed_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    birth_date_estimated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    registration_date: Mapped[date] = mapped_column(
        Date,
        default=lambda: datetime.now(timezone.utc).date(),
        server_default=text("(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date"),
        nullable=False,
    )
    acquisition_date: Mapped[date | None] = mapped_column(Date)
    acquisition_method: Mapped[AcquisitionMethod] = mapped_column(
        Enum(AcquisitionMethod, name="cattle_acquisition_method"),
        default=AcquisitionMethod.UNKNOWN,
        server_default=AcquisitionMethod.UNKNOWN.value,
        nullable=False,
    )
    acquisition_source: Mapped[str | None] = mapped_column(String(255))
    initial_acquisition_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2)
    )
    initial_acquisition_currency: Mapped[str | None] = mapped_column(String(3))
    color: Mapped[str | None] = mapped_column(String(100))
    identification_marks: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[CattleStatus] = mapped_column(
        Enum(CattleStatus, name="cattle_status"),
        default=CattleStatus.ACTIVE,
        server_default=CattleStatus.ACTIVE.value,
        nullable=False,
    )
    mother_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    father_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
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


class CattleWeightRecord(Base):
    __tablename__ = "cattle_weight_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_weight_same_farm",
        ),
        UniqueConstraint(
            "cattle_id", "measured_at", name="uq_cattle_weight_timestamp"
        ),
        CheckConstraint(
            "weight_kg > 0 AND weight_kg <= 3000",
            name="ck_cattle_weight_realistic",
        ),
        Index(
            "ix_cattle_weight_history",
            "farm_id",
            "cattle_id",
            "measured_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(7, 2), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    measurement_method: Mapped[str | None] = mapped_column(String(50))
    recorded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CattleLifecycleEvent(Base):
    __tablename__ = "cattle_lifecycle_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_lifecycle_same_farm",
        ),
        CheckConstraint(
            "previous_status IS NULL OR previous_status <> new_status",
            name="ck_cattle_lifecycle_status_changed",
        ),
        Index(
            "ix_cattle_lifecycle_history",
            "farm_id",
            "cattle_id",
            "effective_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    previous_status: Mapped[CattleStatus | None] = mapped_column(
        Enum(CattleStatus, name="cattle_status", create_type=False)
    )
    new_status: Mapped[CattleStatus] = mapped_column(
        Enum(CattleStatus, name="cattle_status", create_type=False), nullable=False
    )
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CattleMedia(Base):
    __tablename__ = "cattle_media"
    __table_args__ = (
        ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_media_same_farm",
        ),
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 10485760",
            name="ck_cattle_media_size",
        ),
        Index(
            "ix_cattle_media_active",
            "farm_id",
            "cattle_id",
            "uploaded_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    cattle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    farm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    purpose: Mapped[MediaPurpose] = mapped_column(
        Enum(MediaPurpose, name="cattle_media_purpose"), nullable=False
    )
    uploaded_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
