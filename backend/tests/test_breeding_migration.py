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

import app.models  # noqa: F401
from app.db.base import Base


pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[1]
TABLES = {"heat_observations", "breeding_events", "pregnancy_examinations", "pregnancy_losses", "calving_events", "calving_offspring", "parentage_verifications", "breeding_reminders", "breeding_audit_events"}


def test_breeding_migration_upgrade_downgrade_reupgrade_isolated():
    url = os.environ["TEST_DATABASE_URL"]
    admin = create_engine(url, pool_pre_ping=True)
    schema = f"icms_test_{uuid.uuid4().hex}"
    engine = None
    created = False
    try:
        with admin.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "icms_test"
            assert schema != "icms_test_gui_20261017103146_ca6015f2"
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            created = True
        engine = create_engine(url, pool_pre_ping=True, connect_args={"options": f"-csearch_path={schema}"})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            connection.rollback()
            config = Config(str(ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(ROOT / "alembic"))
            config.attributes["connection"] = connection
            command.upgrade(config, "c8d0e1f2a703")
            user_id, farm_id, cow_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            connection.execute(text("INSERT INTO users (id, full_name, email, password_hash, is_system_admin, status, token_version) VALUES (:u, 'Existing', 'breeding-migration@example.com', 'x', false, 'ACTIVE', 0)"), {"u": user_id})
            connection.execute(text("INSERT INTO farms (id, name, owner_id) VALUES (:f, 'Existing Farm', :u)"), {"f": farm_id, "u": user_id})
            connection.execute(text("INSERT INTO farm_members (id, farm_id, user_id, role, status) VALUES (:m, :f, :u, 'FARM_OWNER', 'ACTIVE')"), {"m": uuid.uuid4(), "f": farm_id, "u": user_id})
            connection.execute(text("INSERT INTO cattle (id, farm_id, tag_number, normalized_tag, species, sex, category, created_by_id) VALUES (:c, :f, 'COW-1', 'cow-1', 'CATTLE', 'FEMALE', 'COW', :u)"), {"c": cow_id, "f": farm_id, "u": user_id})
            connection.commit()

            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b3d5f7a9c210"
            assert TABLES <= set(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT count(*) FROM cattle")) == 1
            assert connection.scalar(text("SELECT count(*) FROM permissions WHERE code LIKE 'breeding.%'")) == 8
            assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata) == []

            command.downgrade(config, "c8d0e1f2a703")
            assert not (TABLES & set(inspect(connection).get_table_names()))
            assert connection.scalar(text("SELECT count(*) FROM cattle")) == 1
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b3d5f7a9c210"
            command.downgrade(config, "base")
    finally:
        if engine: engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}", schema)
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
