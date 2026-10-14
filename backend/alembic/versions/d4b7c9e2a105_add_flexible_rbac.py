
"""Add flexible farm RBAC tables and permissions.

Revision ID: d4b7c9e2a105
Revises: c3a1f5e8d9b2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4b7c9e2a105"
down_revision = "c3a1f5e8d9b2"
branch_labels = None
depends_on = None


PERMISSION_CODES = [
    "farm.view",
    "farm.manage",
    "staff.view",
    "staff.manage",
    "roles.manage",
    "cattle.view",
    "cattle.create",
    "cattle.update",
    "cattle.delete",
    "health.view",
    "health.manage",
    "milk.view",
    "milk.record",
    "milk.manage",
    "feed.view",
    "feed.manage",
    "breeding.view",
    "breeding.manage",
    "finance.view",
    "finance.manage",
    "salary.view",
    "salary.manage",
    "reports.view",
    "reports.export",
]


def upgrade() -> None:
    # Required for composite foreign-key referencing.
    op.create_unique_constraint(
        "uq_farm_members_id_farm",
        "farm_members",
        ["id", "farm_id"],
    )

    # System-defined permission catalog.
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(100), primary_key=True),
        sa.Column("description", sa.String(255), nullable=True),
    )

    # Farm-specific custom roles.
    op.create_table(
        "farm_custom_roles",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("farms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "id",
            "farm_id",
            name="uq_farm_custom_roles_id_farm",
        ),
    )

    op.create_index(
        "ix_farm_custom_roles_farm_id",
        "farm_custom_roles",
        ["farm_id"],
    )

    # Custom role -> permission mapping.
    op.create_table(
        "farm_role_permissions",
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "farm_custom_roles.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),
        sa.Column(
            "permission_code",
            sa.String(100),
            sa.ForeignKey(
                "permissions.code",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "role_id",
            "permission_code",
            name="pk_farm_role_permissions",
        ),
    )

    # Farm membership -> custom role assignment.
    op.create_table(
        "farm_member_roles",
        sa.Column(
            "member_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "role_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "farm_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint(
            "member_id",
            "role_id",
            name="pk_farm_member_roles",
        ),
        sa.ForeignKeyConstraint(
            ["role_id", "farm_id"],
            [
                "farm_custom_roles.id",
                "farm_custom_roles.farm_id",
            ],
            ondelete="CASCADE",
            name="fk_member_role_same_farm_role",
        ),
        sa.ForeignKeyConstraint(
            ["member_id", "farm_id"],
            [
                "farm_members.id",
                "farm_members.farm_id",
            ],
            ondelete="CASCADE",
            name="fk_member_role_same_farm_member",
        ),
    )
    op.create_index(
        "uq_farm_custom_roles_farm_name",
        "farm_custom_roles",
        ["farm_id", sa.text("lower(btrim(name))")],
        unique=True,
    )
    op.create_index(
        "ix_farm_member_roles_farm_id",
        "farm_member_roles",
        ["farm_id"],
    )
    op.create_index(
        "ix_farm_member_roles_role_id",
        "farm_member_roles",
        ["role_id"],
    )

    # Seed all available permission codes.
    permission_table = sa.table(
        "permissions",
        sa.column("code", sa.String(100)),
        sa.column("description", sa.String(255)),
    )

    op.bulk_insert(
        permission_table,
        [
            {"code": code, "description": None}
            for code in PERMISSION_CODES
        ],
    )


def downgrade() -> None:
    # Only safe on a disposable test schema.
    # Dropping these tables also removes custom role assignments.
    op.drop_index(
        "ix_farm_member_roles_role_id",
        table_name="farm_member_roles",
    )
    op.drop_index(
        "ix_farm_member_roles_farm_id",
        table_name="farm_member_roles",
    )
    op.drop_table("farm_member_roles")
    op.drop_table("farm_role_permissions")

    op.drop_index(
        "uq_farm_custom_roles_farm_name",
        table_name="farm_custom_roles",
    )
    op.drop_index(
        "ix_farm_custom_roles_farm_id",
        table_name="farm_custom_roles",
    )

    op.drop_table("farm_custom_roles")
    op.drop_table("permissions")

    op.drop_constraint(
        "uq_farm_members_id_farm",
        "farm_members",
        type_="unique",
    )
