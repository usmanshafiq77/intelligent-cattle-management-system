
import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401
from app.core.permissions import PERMISSION_CODES
from app.db.base import Base


pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Permissions introduced by Step 17
STEP_17_HEALTH_PERMISSIONS = {
    "health.create",
    "health.diagnosis",
    "health.vaccination.manage",
    "health.vaccination.administer",
    "health.treatment.manage",
    "health.medication.administer",
    "health.visit.manage",
    "health.audit.view",
}

# Permissions introduced by Step 18
STEP_18_MILK_PERMISSIONS = {
    "milk.lactation.manage",
    "milk.quality.manage",
    "milk.bulk.create",
    "milk.correct",
    "milk.analytics.view",
}


def test_health_migration_lifecycle_seed_and_tenant_constraints():
    database_url = os.environ["TEST_DATABASE_URL"]

    # Never allow this migration test to run against icms_db.
    from sqlalchemy.engine import make_url

    assert make_url(database_url).database == "icms_test", (
        "UNSAFE DATABASE: migration tests must use icms_test"
    )

    admin_engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    schema_name = f"icms_test_{uuid.uuid4().hex}"
    created = False
    migration_engine = None

    try:
        # Create an isolated test schema.
        with admin_engine.begin() as connection:
            assert connection.scalar(
                text("SELECT current_database()")
            ) == "icms_test"

            connection.execute(
                text(f'CREATE SCHEMA "{schema_name}"')
            )
            created = True

        migration_engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={
                "options": f"-csearch_path={schema_name}"
            },
        )

        with migration_engine.connect() as connection:
            assert connection.scalar(
                text("SELECT current_database()")
            ) == "icms_test"

            assert connection.scalar(
                text("SELECT current_schema()")
            ) == schema_name

            connection.rollback()

            # Configure Alembic for the isolated schema.
            config = Config(str(BACKEND_ROOT / "alembic.ini"))

            config.set_main_option(
                "script_location",
                str(BACKEND_ROOT / "alembic"),
            )

            config.attributes["connection"] = connection

            # First migrate to Step 16.5.
            command.upgrade(config, "e6f1a2b3c4d5")

            assert connection.scalar(
                text("SELECT count(*) FROM permissions")
            ) == 24

            # Apply Step 17 health migration.
            command.upgrade(config, "f7a2b3c4d5e6")

            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "f7a2b3c4d5e6"

            # Step 17 contains 32 permissions.
            expected_step17_permissions = (
                set(PERMISSION_CODES) - STEP_18_MILK_PERMISSIONS
            )

            actual_step17_permissions = set(
                connection.scalars(
                    text("SELECT code FROM permissions")
                )
            )

            assert len(actual_step17_permissions) == 32
            assert actual_step17_permissions == expected_step17_permissions
            assert STEP_17_HEALTH_PERMISSIONS <= actual_step17_permissions
            assert not STEP_18_MILK_PERMISSIONS.intersection(
                actual_step17_permissions
            )

            # Verify all Step 17 health tables exist.
            health_tables = {
                "health_encounters",
                "health_diagnoses",
                "vaccination_schedules",
                "vaccination_administrations",
                "treatment_plans",
                "medication_administrations",
                "veterinary_visits",
                "health_record_corrections",
            }

            actual_tables = set(
                inspect(connection).get_table_names()
            )

            assert health_tables <= actual_tables

            # Step 18 tables should not exist at Step 17 revision.
            step18_tables = {
                "milk_lactations",
                "milking_sessions",
                "milk_quality_measurements",
                "milk_record_corrections",
            }

            assert not step18_tables.intersection(actual_tables)

            # Create two users and farms to test tenant isolation.
            user_a, user_b = uuid.uuid4(), uuid.uuid4()
            farm_a, farm_b, cattle_a = (
                uuid.uuid4(),
                uuid.uuid4(),
                uuid.uuid4(),
            )

            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, full_name, email, password_hash, "
                    "is_system_admin, status) "
                    "VALUES "
                    "(:a, 'A', 'health-migration-a@example.com', "
                    "'x', false, 'ACTIVE'), "
                    "(:b, 'B', 'health-migration-b@example.com', "
                    "'x', false, 'ACTIVE')"
                ),
                {
                    "a": user_a,
                    "b": user_b,
                },
            )

            connection.execute(
                text(
                    "INSERT INTO farms "
                    "(id, name, owner_id) "
                    "VALUES "
                    "(:a, 'A', :ua), "
                    "(:b, 'B', :ub)"
                ),
                {
                    "a": farm_a,
                    "b": farm_b,
                    "ua": user_a,
                    "ub": user_b,
                },
            )

            connection.execute(
                text(
                    "INSERT INTO farm_members "
                    "(id, farm_id, user_id, role, status) "
                    "VALUES "
                    "(:ma, :fa, :ua, 'FARM_OWNER', 'ACTIVE'), "
                    "(:mb, :fb, :ub, 'FARM_OWNER', 'ACTIVE')"
                ),
                {
                    "ma": uuid.uuid4(),
                    "mb": uuid.uuid4(),
                    "fa": farm_a,
                    "fb": farm_b,
                    "ua": user_a,
                    "ub": user_b,
                },
            )

            connection.execute(
                text(
                    "INSERT INTO cattle "
                    "(id, farm_id, tag_number, normalized_tag, "
                    "species, sex, category, created_by_id) "
                    "VALUES "
                    "(:id, :farm, 'A-1', 'a-1', "
                    "'CATTLE', 'FEMALE', 'COW', :user)"
                ),
                {
                    "id": cattle_a,
                    "farm": farm_a,
                    "user": user_a,
                },
            )

            connection.commit()

            # Verify PostgreSQL rejects cross-farm health records.
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO health_encounters "
                        "(id, farm_id, cattle_id, encounter_type, "
                        "status, occurred_at, created_by_id) "
                        "VALUES "
                        "(:id, :farm, :cattle, "
                        "'ROUTINE', 'DRAFT', now(), :user)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "farm": farm_b,
                        "cattle": cattle_a,
                        "user": user_b,
                    },
                )

                connection.commit()

            connection.rollback()

            # Verify Step 17 downgrade.
            command.downgrade(config, "e6f1a2b3c4d5")

            assert "health_encounters" not in set(
                inspect(connection).get_table_names()
            )

            assert connection.scalar(
                text("SELECT count(*) FROM permissions")
            ) == 24

            connection.rollback()

            # Get the latest revision dynamically.
            script = ScriptDirectory.from_config(config)
            expected_head = script.get_current_head()

            assert expected_head is not None

            # Re-upgrade to the latest revision, including Step 18.
            command.upgrade(config, "head")

            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == expected_head

            # At the current head, DB schema and ORM models
            # must match exactly.
            migration_context = MigrationContext.configure(
                connection,
                opts={"compare_type": True},
            )

            assert compare_metadata(
                migration_context,
                Base.metadata,
            ) == []

            connection.rollback()

            # Cleanup inside disposable test schema.
            command.downgrade(config, "base")

    finally:
        if migration_engine is not None:
            migration_engine.dispose()

        if created:
            assert re.fullmatch(
                r"icms_test_[0-9a-f]{32}",
                schema_name,
            )

            with admin_engine.begin() as connection:
                assert connection.scalar(
                    text("SELECT current_database()")
                ) == "icms_test"

                connection.execute(
                    text(f'DROP SCHEMA "{schema_name}" CASCADE')
                )

        admin_engine.dispose()
