import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[1]
TABLES = {"operational_tasks", "task_assignments", "task_activities", "worker_cattle_assignments", "app_notifications", "notification_preferences", "notification_delivery_attempts"}


def test_work_management_migration_isolated_upgrade_and_downgrade():
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
            config = Config(str(ROOT / "alembic.ini")); config.set_main_option("script_location", str(ROOT / "alembic")); config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b3d5f7a9c210"
            assert TABLES <= set(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT count(*) FROM permissions WHERE code = ANY(ARRAY['task.view','task.manage','task.update.assigned','cattle.assignment.manage','notification.view'])")) == 5
            command.downgrade(config, "f1a3b5c7d906")
            assert not (TABLES & set(inspect(connection).get_table_names()))
    finally:
        if engine: engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}", schema)
            with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
