"""add security foundation constraints and email verification

Revision ID: c3a1f5e8d9b2
Revises: b9f8ee48d20d
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3a1f5e8d9b2"
down_revision: Union[str, Sequence[str], None] = "b9f8ee48d20d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _abort_on_unsafe_existing_data() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM invitations
                    WHERE status = 'PENDING'::invitation_status
                    GROUP BY farm_id, lower(btrim(email))
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'Security migration blocked: duplicate pending '
                        'invitations exist for a farm/email identity.';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM invitations
                    WHERE role = 'FARM_OWNER'::farm_role
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'Security migration blocked: an invitation contains '
                        'the FARM_OWNER role.';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM farm_members
                    WHERE role = 'FARM_OWNER'::farm_role
                      AND status <> 'ACTIVE'::member_status
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'Security migration blocked: an owner membership is '
                        'not active.';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM farm_members
                    WHERE role = 'FARM_OWNER'::farm_role
                      AND status = 'ACTIVE'::member_status
                    GROUP BY farm_id
                    HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'Security migration blocked: a farm has multiple '
                        'active owner memberships.';
                END IF;

                IF EXISTS (
                    SELECT 1
                    FROM farms AS f
                    LEFT JOIN farm_members AS fm
                      ON fm.farm_id = f.id
                     AND fm.user_id = f.owner_id
                     AND fm.role = 'FARM_OWNER'::farm_role
                     AND fm.status = 'ACTIVE'::member_status
                    WHERE fm.id IS NULL
                ) THEN
                    RAISE EXCEPTION USING MESSAGE =
                        'Security migration blocked: farms.owner_id does not '
                        'have a matching active FARM_OWNER membership.';
                END IF;
            END
            $$;
            """
        )
    )


def upgrade() -> None:
    _abort_on_unsafe_existing_data()

    op.add_column(
        "users",
        sa.Column(
            "email_verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.create_check_constraint(
        "ck_farm_members_owner_is_active",
        "farm_members",
        "role <> 'FARM_OWNER' OR status = 'ACTIVE'",
    )
    op.create_check_constraint(
        "ck_invitations_no_owner_role",
        "invitations",
        "role <> 'FARM_OWNER'",
    )

    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_farm_members_one_active_owner
            ON farm_members (farm_id)
            WHERE role = 'FARM_OWNER'::farm_role
              AND status = 'ACTIVE'::member_status
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_invitations_pending_farm_email
            ON invitations (farm_id, lower(btrim(email)))
            WHERE status = 'PENDING'::invitation_status
            """
        )
    )

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
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
            "used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "token_hash",
            name="uq_email_verification_tokens_token_hash",
        ),
    )
    op.create_index(
        "ix_email_verification_tokens_user_id",
        "email_verification_tokens",
        ["user_id"],
    )
    op.execute(
        sa.text(
            """
            CREATE UNIQUE INDEX uq_email_verification_tokens_one_active
            ON email_verification_tokens (user_id)
            WHERE used_at IS NULL AND revoked_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        "uq_email_verification_tokens_one_active",
        table_name="email_verification_tokens",
    )
    op.drop_index(
        "ix_email_verification_tokens_user_id",
        table_name="email_verification_tokens",
    )
    op.drop_table("email_verification_tokens")

    op.drop_index(
        "uq_invitations_pending_farm_email",
        table_name="invitations",
    )
    op.drop_index(
        "uq_farm_members_one_active_owner",
        table_name="farm_members",
    )
    op.drop_constraint(
        "ck_invitations_no_owner_role",
        "invitations",
        type_="check",
    )
    op.drop_constraint(
        "ck_farm_members_owner_is_active",
        "farm_members",
        type_="check",
    )
    op.drop_column("users", "email_verified_at")
