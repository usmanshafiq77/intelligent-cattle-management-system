import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PermissionRecord(Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str | None] = mapped_column(String(255))


class FarmCustomRole(Base):
    __tablename__ = "farm_custom_roles"
    __table_args__ = (
        UniqueConstraint(
            "id", "farm_id", name="uq_farm_custom_roles_id_farm"
        ),
        Index(
            "uq_farm_custom_roles_farm_name",
            "farm_id",
            text("lower(btrim(name))"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FarmRolePermission(Base):
    __tablename__ = "farm_role_permissions"
    __table_args__ = (
        PrimaryKeyConstraint(
            "role_id",
            "permission_code",
            name="pk_farm_role_permissions",
        ),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("farm_custom_roles.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission_code: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("permissions.code", ondelete="RESTRICT"),
        nullable=False,
    )


class FarmMemberRole(Base):
    __tablename__ = "farm_member_roles"
    __table_args__ = (
        PrimaryKeyConstraint(
            "member_id", "role_id", name="pk_farm_member_roles"
        ),
        ForeignKeyConstraint(
            ["role_id", "farm_id"],
            ["farm_custom_roles.id", "farm_custom_roles.farm_id"],
            ondelete="CASCADE",
            name="fk_member_role_same_farm_role",
        ),
        ForeignKeyConstraint(
            ["member_id", "farm_id"],
            ["farm_members.id", "farm_members.farm_id"],
            ondelete="CASCADE",
            name="fk_member_role_same_farm_member",
        ),
        Index("ix_farm_member_roles_farm_id", "farm_id"),
        Index("ix_farm_member_roles_role_id", "role_id"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    farm_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
