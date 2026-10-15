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


def test_milk_migration_lifecycle_metadata_seeds_and_constraints():
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
            database_url, pool_pre_ping=True,
            connect_args={"options": f"-csearch_path={schema_name}"},
        )
        with migration_engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "icms_test"
            assert connection.scalar(text("SELECT current_schema()")) == schema_name
            connection.rollback()
            config = Config(str(BACKEND_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
            config.attributes["connection"] = connection
            command.upgrade(config, "f7a2b3c4d5e6")
            user_id, farm_id, cattle_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            connection.execute(text(
                "INSERT INTO users (id, full_name, email, password_hash, is_system_admin, status) "
                "VALUES (:u, 'Existing', 'milk-migration@example.com', 'x', false, 'ACTIVE')"
            ), {"u": user_id})
            connection.execute(text("INSERT INTO farms (id, name, owner_id) VALUES (:f, 'Existing', :u)"), {"f": farm_id, "u": user_id})
            connection.execute(text(
                "INSERT INTO farm_members (id, farm_id, user_id, role, status) "
                "VALUES (:m, :f, :u, 'FARM_OWNER', 'ACTIVE')"
            ), {"m": uuid.uuid4(), "f": farm_id, "u": user_id})
            connection.execute(text(
                "INSERT INTO cattle (id, farm_id, tag_number, normalized_tag, species, sex, category, created_by_id) "
                "VALUES (:c, :f, 'M-1', 'm-1', 'CATTLE', 'FEMALE', 'COW', :u)"
            ), {"c": cattle_id, "f": farm_id, "u": user_id})
            connection.commit()
            command.upgrade(config, "a8b3c4d5e6f7")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a8b3c4d5e6f7"
            assert set(connection.scalars(text("SELECT code FROM permissions"))) == set(PERMISSION_CODES)
            assert connection.scalar(text("SELECT count(*) FROM cattle")) == 1
            assert {"milk_lactations", "milking_sessions", "milk_quality_measurements", "milk_record_corrections"} <= set(inspect(connection).get_table_names())
            assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata) == []
            lactation_id = uuid.uuid4()
            connection.execute(text(
                "INSERT INTO milk_lactations (id, farm_id, cattle_id, sequence_number, start_date, created_by_id) "
                "VALUES (:l, :f, :c, 1, '2026-01-01', :u)"
            ), {"l": lactation_id, "f": farm_id, "c": cattle_id, "u": user_id})
            connection.commit()
            with pytest.raises(IntegrityError):
                connection.execute(text(
                    "INSERT INTO milk_lactations (id, farm_id, cattle_id, sequence_number, start_date, created_by_id) "
                    "VALUES (:l, :f, :c, 2, '2026-02-01', :u)"
                ), {"l": uuid.uuid4(), "f": farm_id, "c": cattle_id, "u": user_id})
                connection.commit()
            connection.rollback()
            command.downgrade(config, "f7a2b3c4d5e6")
            assert "milk_lactations" not in set(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT count(*) FROM cattle")) == 1
            assert connection.scalar(text("SELECT count(*) FROM permissions")) == 32
            connection.rollback()
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT count(*) FROM permissions")) == len(PERMISSION_CODES)
            command.downgrade(config, "base")
    finally:
        if migration_engine is not None:
            migration_engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}", schema_name)
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        admin_engine.dispose()
