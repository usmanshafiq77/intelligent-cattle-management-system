import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401
from app.core.permissions import PERMISSION_CODES
from app.db.base import Base


pytestmark = pytest.mark.integration
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_health_migration_lifecycle_seed_and_tenant_constraints():
    database_url = os.environ["TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    schema_name = f"icms_test_{uuid.uuid4().hex}"
    created = False
    migration_engine = None
    try:
        with admin_engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "icms_test"
            connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
            created = True

        migration_engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema_name}"},
        )
        with migration_engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "icms_test"
            assert connection.scalar(text("SELECT current_schema()")) == schema_name
            connection.rollback()
            config = Config(str(BACKEND_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
            config.attributes["connection"] = connection

            command.upgrade(config, "e6f1a2b3c4d5")
            assert connection.scalar(text("SELECT count(*) FROM permissions")) == 24
            command.upgrade(config, "f7a2b3c4d5e6")
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "f7a2b3c4d5e6"
            assert set(connection.scalars(text("SELECT code FROM permissions"))) == set(
                PERMISSION_CODES
            )
            assert {
                "health_encounters",
                "health_diagnoses",
                "vaccination_schedules",
                "vaccination_administrations",
                "treatment_plans",
                "medication_administrations",
                "veterinary_visits",
                "health_record_corrections",
            } <= set(inspect(connection).get_table_names())
            assert compare_metadata(
                MigrationContext.configure(
                    connection, opts={"compare_type": True}
                ),
                Base.metadata,
            ) == []

            user_a, user_b = uuid.uuid4(), uuid.uuid4()
            farm_a, farm_b, cattle_a = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, full_name, email, password_hash, is_system_admin, status) "
                    "VALUES (:a, 'A', 'health-migration-a@example.com', 'x', false, 'ACTIVE'), "
                    "(:b, 'B', 'health-migration-b@example.com', 'x', false, 'ACTIVE')"
                ),
                {"a": user_a, "b": user_b},
            )
            connection.execute(
                text(
                    "INSERT INTO farms (id, name, owner_id) VALUES "
                    "(:a, 'A', :ua), (:b, 'B', :ub)"
                ),
                {"a": farm_a, "b": farm_b, "ua": user_a, "ub": user_b},
            )
            connection.execute(
                text(
                    "INSERT INTO farm_members "
                    "(id, farm_id, user_id, role, status) VALUES "
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
                    "(id, farm_id, tag_number, normalized_tag, species, sex, "
                    "category, created_by_id) VALUES "
                    "(:id, :farm, 'A-1', 'a-1', 'CATTLE', 'FEMALE', 'COW', :user)"
                ),
                {"id": cattle_a, "farm": farm_a, "user": user_a},
            )
            connection.commit()
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO health_encounters "
                        "(id, farm_id, cattle_id, encounter_type, status, "
                        "occurred_at, created_by_id) VALUES "
                        "(:id, :farm, :cattle, 'ROUTINE', 'DRAFT', now(), :user)"
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

            command.downgrade(config, "e6f1a2b3c4d5")
            assert "health_encounters" not in set(
                inspect(connection).get_table_names()
            )
            assert connection.scalar(text("SELECT count(*) FROM permissions")) == 24
            connection.rollback()
            command.upgrade(config, "head")
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "f7a2b3c4d5e6"
            connection.rollback()
            command.downgrade(config, "base")
    finally:
        if migration_engine is not None:
            migration_engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}", schema_name)
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        admin_engine.dispose()
