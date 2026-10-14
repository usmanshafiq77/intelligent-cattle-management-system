
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FarmRole(str, enum.Enum):
    FARM_OWNER = "FARM_OWNER"
    FARM_MANAGER = "FARM_MANAGER"
    WORKER = "WORKER"
    VETERINARIAN = "VETERINARIAN"


class MemberStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    PENDING = "PENDING"
    INACTIVE = "INACTIVE"


class FarmMember(Base):
    __tablename__ = "farm_members"

    __table_args__ = (
        UniqueConstraint(
            "farm_id",
            "user_id",
            name="uq_farm_members_farm_user",
        ),
        UniqueConstraint(
            "id",
            "farm_id",
            name="uq_farm_members_id_farm",
        ),
        CheckConstraint(
            "role <> 'FARM_OWNER' OR status = 'ACTIVE'",
            name="ck_farm_members_owner_is_active",
        ),
        Index(
            "uq_farm_members_one_active_owner",
            "farm_id",
            unique=True,
            postgresql_where=text(
                "role = 'FARM_OWNER' AND status = 'ACTIVE'"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role: Mapped[FarmRole] = mapped_column(
        Enum(FarmRole, name="farm_role"),
        nullable=False,
    )

    status: Mapped[MemberStatus] = mapped_column(
        Enum(MemberStatus, name="member_status"),
        default=MemberStatus.ACTIVE,
        nullable=False,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
