
"""Add password reset security support.

Revision ID: b7c9d2e4f601
Revises: a8b3c4d5e6f7
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "b7c9d2e4f601"
down_revision: Union[str, None] = "a8b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "token_version",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
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
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_password_reset_tokens_token_hash",
        ),
    )

    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        ["user_id"],
        unique=False,
    )

    op.create_index(
        "uq_password_reset_tokens_one_active",
        "password_reset_tokens",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text(
            "used_at IS NULL AND revoked_at IS NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_password_reset_tokens_one_active",
        table_name="password_reset_tokens",
    )

    op.drop_index(
        "ix_password_reset_tokens_user_id",
        table_name="password_reset_tokens",
    )

    op.drop_table("password_reset_tokens")

    op.drop_column("users", "token_version")
