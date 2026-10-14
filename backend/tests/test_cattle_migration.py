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
from app.db.base import Base


pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_cattle_migration_upgrade_downgrade_and_tenant_constraints():
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
            search_path = connection.scalar(text("SHOW search_path"))
            assert schema_name in search_path
            connection.rollback()

            config = Config(str(BACKEND_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
            config.attributes["connection"] = connection
            command.upgrade(config, "d4b7c9e2a105")
            command.upgrade(config, "e6f1a2b3c4d5")

            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "e6f1a2b3c4d5"
            assert connection.scalar(text("SELECT count(*) FROM breeds")) == 9
            tables = set(inspect(connection).get_table_names())
            assert {
                "breeds",
                "cattle",
                "cattle_weight_records",
                "cattle_lifecycle_events",
                "cattle_media",
            } <= tables
            migration_context = MigrationContext.configure(
                connection, opts={"compare_type": True}
            )
            assert compare_metadata(migration_context, Base.metadata) == []

            user_a, user_b = uuid.uuid4(), uuid.uuid4()
            farm_a, farm_b, cattle_a = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            for user_id, suffix in ((user_a, "a"), (user_b, "b")):
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id, full_name, email, password_hash, is_system_admin, status) "
                        "VALUES (:id, 'Migration User', :email, 'unused', false, 'ACTIVE')"
                    ),
                    {"id": user_id, "email": f"cattle-migration-{suffix}@example.com"},
                )
            connection.execute(
                text(
                    "INSERT INTO farms (id, name, owner_id) VALUES "
                    "(:a, 'A', :user_a), (:b, 'B', :user_b)"
                ),
                {"a": farm_a, "b": farm_b, "user_a": user_a, "user_b": user_b},
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
                        "INSERT INTO cattle_weight_records "
                        "(id, cattle_id, farm_id, weight_kg, measured_at, recorded_by_id) "
                        "VALUES (:id, :cattle, :farm, 400, now(), :user)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "cattle": cattle_a,
                        "farm": farm_b,
                        "user": user_b,
                    },
                )
                connection.commit()
            connection.rollback()

            command.downgrade(config, "d4b7c9e2a105")
            assert "cattle" not in set(inspect(connection).get_table_names())
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "d4b7c9e2a105"
            connection.rollback()
            command.upgrade(config, "head")
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "e6f1a2b3c4d5"
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
