
"""create initial ICMS tables

Revision ID: b9f8ee48d20d
Revises:
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b9f8ee48d20d"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# PostgreSQL ENUM types
user_status = postgresql.ENUM(
    "ACTIVE",
    "PENDING",
    "INACTIVE",
    name="user_status",
    create_type=False,
)

farm_role = postgresql.ENUM(
    "FARM_OWNER",
    "FARM_MANAGER",
    "WORKER",
    "VETERINARIAN",
    name="farm_role",
    create_type=False,
)

member_status = postgresql.ENUM(
    "ACTIVE",
    "PENDING",
    "INACTIVE",
    name="member_status",
    create_type=False,
)

invitation_status = postgresql.ENUM(
    "PENDING",
    "ACCEPTED",
    "REJECTED",
    "EXPIRED",
    "REVOKED",
    name="invitation_status",
    create_type=False,
)


def upgrade() -> None:
    # Create each PostgreSQL ENUM exactly once.
    user_status.create(op.get_bind(), checkfirst=True)
    farm_role.create(op.get_bind(), checkfirst=True)
    member_status.create(op.get_bind(), checkfirst=True)
    invitation_status.create(op.get_bind(), checkfirst=True)

    # USERS
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_system_admin", sa.Boolean(), nullable=False),
        sa.Column("status", user_status, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
    )

    # FARMS
    op.create_table(
        "farms",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_farms_owner_id",
        "farms",
        ["owner_id"],
    )

    # FARM MEMBERS
    op.create_table(
        "farm_members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role", farm_role, nullable=False),
        sa.Column("status", member_status, nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farms.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "farm_id",
            "user_id",
            name="uq_farm_members_farm_user",
        ),
    )

    op.create_index(
        "ix_farm_members_farm_id",
        "farm_members",
        ["farm_id"],
    )

    op.create_index(
        "ix_farm_members_user_id",
        "farm_members",
        ["user_id"],
    )

    # INVITATIONS
    op.create_table(
        "invitations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("invited_by_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("role", farm_role, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "status",
            invitation_status,
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farms.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )

    op.create_index(
        "ix_invitations_email",
        "invitations",
        ["email"],
    )

    op.create_index(
        "ix_invitations_farm_id",
        "invitations",
        ["farm_id"],
    )


def downgrade() -> None:
    # Drop tables in reverse dependency order.
    op.drop_index(
        "ix_invitations_farm_id",
        table_name="invitations",
    )
    op.drop_index(
        "ix_invitations_email",
        table_name="invitations",
    )
    op.drop_table("invitations")

    op.drop_index(
        "ix_farm_members_user_id",
        table_name="farm_members",
    )
    op.drop_index(
        "ix_farm_members_farm_id",
        table_name="farm_members",
    )
    op.drop_table("farm_members")

    op.drop_index(
        "ix_farms_owner_id",
        table_name="farms",
    )
    op.drop_table("farms")

    op.drop_index(
        "ix_users_email",
        table_name="users",
    )
    op.drop_table("users")

    # Remove PostgreSQL ENUM types.
    invitation_status.drop(op.get_bind(), checkfirst=True)
    member_status.drop(op.get_bind(), checkfirst=True)
    farm_role.drop(op.get_bind(), checkfirst=True)
    user_status.drop(op.get_bind(), checkfirst=True)
