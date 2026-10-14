"""Add cattle registration and profile management.

Revision ID: e6f1a2b3c4d5
Revises: d4b7c9e2a105
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e6f1a2b3c4d5"
down_revision = "d4b7c9e2a105"
branch_labels = None
depends_on = None


species_enum = postgresql.ENUM(
    "CATTLE", "BUFFALO", name="cattle_species", create_type=False
)
sex_enum = postgresql.ENUM(
    "FEMALE", "MALE", name="cattle_sex", create_type=False
)
category_enum = postgresql.ENUM(
    "CALF",
    "HEIFER",
    "COW",
    "BULL",
    "STEER",
    "OTHER",
    name="cattle_category",
    create_type=False,
)
status_enum = postgresql.ENUM(
    "ACTIVE",
    "SOLD",
    "DECEASED",
    "TRANSFERRED",
    "MISSING",
    "ARCHIVED",
    name="cattle_status",
    create_type=False,
)
acquisition_enum = postgresql.ENUM(
    "BORN_ON_FARM",
    "PURCHASED",
    "TRANSFERRED_IN",
    "DONATED",
    "OTHER",
    "UNKNOWN",
    name="cattle_acquisition_method",
    create_type=False,
)
media_purpose_enum = postgresql.ENUM(
    "PROFILE",
    "IDENTIFICATION",
    "HEALTH",
    "OTHER",
    name="cattle_media_purpose",
    create_type=False,
)


BREEDS = [
    ("15a83daf-5c4a-5cb9-8bed-5a4e7ea1e035", "CATTLE", "Holstein"),
    ("c91361cd-6a4c-5ae6-95d0-e7171de26ab0", "CATTLE", "Jersey"),
    ("c3c588d1-3022-52a7-9444-daa947f986a7", "CATTLE", "Sahiwal"),
    ("0b77e445-1603-53f6-b51e-1d50e77e1624", "CATTLE", "Red Sindhi"),
    ("a7acd555-8347-5e4c-9d40-d6461886e6a6", "CATTLE", "Tharparkar"),
    ("14436bee-1a9a-58e5-8436-510fe5b9b03c", "CATTLE", "Crossbred"),
    ("7e9a2385-f882-51c4-9940-c9c9fb2ea34e", "BUFFALO", "Nili-Ravi"),
    ("3b10a19e-51f5-5241-87d1-8ee915bd8db0", "BUFFALO", "Kundi"),
    ("f6be903c-daf6-5255-a1bd-22d42c685021", "BUFFALO", "Murrah"),
]


def upgrade() -> None:
    bind = op.get_bind()
    species_enum.create(bind, checkfirst=True)
    sex_enum.create(bind, checkfirst=True)
    category_enum.create(bind, checkfirst=True)
    status_enum.create(bind, checkfirst=True)
    acquisition_enum.create(bind, checkfirst=True)
    media_purpose_enum.create(bind, checkfirst=True)

    op.create_table(
        "breeds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("species", species_enum, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("normalized_name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default="true", nullable=False
        ),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "species", "normalized_name", name="uq_breeds_species_name"
        ),
        sa.UniqueConstraint("id", "species", name="uq_breeds_id_species"),
    )
    op.create_index("ix_breeds_species", "breeds", ["species"])

    breed_table = sa.table(
        "breeds",
        sa.column("id", sa.UUID()),
        sa.column("species", species_enum),
        sa.column("name", sa.String(100)),
        sa.column("normalized_name", sa.String(100)),
        sa.column("description", sa.String(500)),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        breed_table,
        [
            {
                "id": breed_id,
                "species": species,
                "name": name,
                "normalized_name": name.casefold(),
                "description": None,
                "is_active": True,
            }
            for breed_id, species, name in BREEDS
        ],
    )

    op.create_table(
        "cattle",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("tag_number", sa.String(100), nullable=False),
        sa.Column("normalized_tag", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=True),
        sa.Column("species", species_enum, nullable=False),
        sa.Column("sex", sex_enum, nullable=False),
        sa.Column("category", category_enum, nullable=False),
        sa.Column("breed_id", sa.UUID(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column(
            "birth_date_estimated",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column(
            "registration_date",
            sa.Date(),
            server_default=sa.text(
                "(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date"
            ),
            nullable=False,
        ),
        sa.Column("acquisition_date", sa.Date(), nullable=True),
        sa.Column(
            "acquisition_method",
            acquisition_enum,
            server_default="UNKNOWN",
            nullable=False,
        ),
        sa.Column("acquisition_source", sa.String(255), nullable=True),
        sa.Column("initial_acquisition_cost", sa.Numeric(12, 2), nullable=True),
        sa.Column("initial_acquisition_currency", sa.String(3), nullable=True),
        sa.Column("color", sa.String(100), nullable=True),
        sa.Column("identification_marks", sa.String(500), nullable=True),
        sa.Column(
            "status", status_enum, server_default="ACTIVE", nullable=False
        ),
        sa.Column("mother_id", sa.UUID(), nullable=True),
        sa.Column("father_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
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
        sa.CheckConstraint(
            "category NOT IN ('HEIFER', 'COW') OR sex = 'FEMALE'",
            name="ck_cattle_female_category",
        ),
        sa.CheckConstraint(
            "category NOT IN ('BULL', 'STEER') OR sex = 'MALE'",
            name="ck_cattle_male_category",
        ),
        sa.CheckConstraint(
            "NOT birth_date_estimated OR date_of_birth IS NOT NULL",
            name="ck_cattle_estimated_birth_has_date",
        ),
        sa.CheckConstraint(
            "initial_acquisition_cost IS NULL OR initial_acquisition_cost >= 0",
            name="ck_cattle_acquisition_cost_nonnegative",
        ),
        sa.CheckConstraint(
            "(initial_acquisition_cost IS NULL) = "
            "(initial_acquisition_currency IS NULL)",
            name="ck_cattle_acquisition_money_complete",
        ),
        sa.CheckConstraint(
            "length(btrim(normalized_tag)) > 0",
            name="ck_cattle_normalized_tag_not_empty",
        ),
        sa.CheckConstraint(
            "mother_id IS NULL OR mother_id <> id",
            name="ck_cattle_mother_not_self",
        ),
        sa.CheckConstraint(
            "father_id IS NULL OR father_id <> id",
            name="ck_cattle_father_not_self",
        ),
        sa.CheckConstraint(
            "mother_id IS NULL OR father_id IS NULL OR mother_id <> father_id",
            name="ck_cattle_parents_distinct",
        ),
        sa.ForeignKeyConstraint(
            ["breed_id", "species"],
            ["breeds.id", "breeds.species"],
            ondelete="RESTRICT",
            name="fk_cattle_breed_species",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farms.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["mother_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_mother_same_farm",
        ),
        sa.ForeignKeyConstraint(
            ["father_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_father_same_farm",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "farm_id", "normalized_tag", name="uq_cattle_farm_tag"
        ),
        sa.UniqueConstraint("id", "farm_id", name="uq_cattle_id_farm"),
    )
    op.create_index("ix_cattle_farm_status", "cattle", ["farm_id", "status"])
    op.create_index("ix_cattle_farm_species", "cattle", ["farm_id", "species"])
    op.create_index("ix_cattle_farm_breed", "cattle", ["farm_id", "breed_id"])

    op.create_table(
        "cattle_weight_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("weight_kg", sa.Numeric(7, 2), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("measurement_method", sa.String(50), nullable=True),
        sa.Column("recorded_by_id", sa.UUID(), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "weight_kg > 0 AND weight_kg <= 3000",
            name="ck_cattle_weight_realistic",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_weight_same_farm",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cattle_id", "measured_at", name="uq_cattle_weight_timestamp"
        ),
    )
    op.create_index(
        "ix_cattle_weight_history",
        "cattle_weight_records",
        ["farm_id", "cattle_id", "measured_at"],
    )

    op.create_table(
        "cattle_lifecycle_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("previous_status", status_enum, nullable=True),
        sa.Column("new_status", status_enum, nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "previous_status IS NULL OR previous_status <> new_status",
            name="ck_cattle_lifecycle_status_changed",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_lifecycle_same_farm",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_cattle_lifecycle_history",
        "cattle_lifecycle_events",
        ["farm_id", "cattle_id", "effective_at"],
    )

    op.create_table(
        "cattle_media",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("cattle_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("purpose", media_purpose_enum, nullable=False),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_by_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 10485760",
            name="ck_cattle_media_size",
        ),
        sa.ForeignKeyConstraint(
            ["cattle_id", "farm_id"],
            ["cattle.id", "cattle.farm_id"],
            ondelete="RESTRICT",
            name="fk_cattle_media_same_farm",
        ),
        sa.ForeignKeyConstraint(
            ["removed_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_cattle_media_active",
        "cattle_media",
        ["farm_id", "cattle_id", "uploaded_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cattle_media_active", table_name="cattle_media")
    op.drop_table("cattle_media")
    op.drop_index(
        "ix_cattle_lifecycle_history", table_name="cattle_lifecycle_events"
    )
    op.drop_table("cattle_lifecycle_events")
    op.drop_index(
        "ix_cattle_weight_history", table_name="cattle_weight_records"
    )
    op.drop_table("cattle_weight_records")
    op.drop_index("ix_cattle_farm_breed", table_name="cattle")
    op.drop_index("ix_cattle_farm_species", table_name="cattle")
    op.drop_index("ix_cattle_farm_status", table_name="cattle")
    op.drop_table("cattle")
    op.drop_index("ix_breeds_species", table_name="breeds")
    op.drop_table("breeds")
    media_purpose_enum.drop(op.get_bind(), checkfirst=True)
    acquisition_enum.drop(op.get_bind(), checkfirst=True)
    status_enum.drop(op.get_bind(), checkfirst=True)
    category_enum.drop(op.get_bind(), checkfirst=True)
    sex_enum.drop(op.get_bind(), checkfirst=True)
    species_enum.drop(op.get_bind(), checkfirst=True)
