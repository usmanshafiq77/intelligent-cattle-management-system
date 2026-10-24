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
FEED_TABLES = {
    "feed_items",
    "feed_stock_movements",
    "feeding_schedules",
    "feed_consumption_records",
    "nutrition_plans",
    "nutrition_plan_items",
}
BREEDING_MIGRATION_PERMISSIONS = {
    "breeding.heat.record", "breeding.event.record",
    "breeding.pregnancy.assess", "breeding.calving.record",
    "breeding.pedigree.manage", "breeding.reports.view",
}
FINANCE_MIGRATION_PERMISSIONS = {
    "finance.income.manage", "finance.expense.manage", "finance.sales.manage",
    "finance.payments.manage", "finance.budgets.manage", "finance.assets.manage",
    "finance.reports.view", "finance.audit.view",
}
MARKETPLACE_MIGRATION_PERMISSIONS = {code for code in PERMISSION_CODES if code.startswith("marketplace.")}
WORK_MIGRATION_PERMISSIONS = {"task.view", "task.manage", "task.update.assigned", "cattle.assignment.manage", "notification.view"}


def test_feed_migration_lifecycle_isolated_and_data_safe():
    database_url = os.environ["TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    schema_name = f"icms_test_{uuid.uuid4().hex}"
    created = False
    migration_engine = None
    try:
        with admin_engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == "icms_test"
            protected = connection.scalar(text(
                "SELECT count(*) FROM information_schema.schemata "
                "WHERE schema_name = 'icms_test_gui_20261017103146_ca6015f2'"
            ))
            assert protected in {0, 1}
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
            command.upgrade(config, "b7c9d2e4f601")
            user_id, farm_id = uuid.uuid4(), uuid.uuid4()
            connection.execute(text(
                "INSERT INTO users (id, full_name, email, password_hash, is_system_admin, status, token_version) "
                "VALUES (:u, 'Existing Feed Owner', 'feed-migration@example.com', 'x', false, 'ACTIVE', 0)"
            ), {"u": user_id})
            connection.execute(text(
                "INSERT INTO farms (id, name, owner_id) VALUES (:f, 'Existing Farm', :u)"
            ), {"f": farm_id, "u": user_id})
            connection.commit()

            command.upgrade(config, "c8d0e1f2a703")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "c8d0e1f2a703"
            assert FEED_TABLES <= set(inspect(connection).get_table_names())
            assert set(connection.scalars(text("SELECT code FROM permissions"))) == set(PERMISSION_CODES) - BREEDING_MIGRATION_PERMISSIONS - FINANCE_MIGRATION_PERMISSIONS - MARKETPLACE_MIGRATION_PERMISSIONS - WORK_MIGRATION_PERMISSIONS
            assert connection.scalar(text("SELECT count(*) FROM farms")) == 1

            item_id = uuid.uuid4()
            connection.execute(text(
                "INSERT INTO feed_items "
                "(id, farm_id, name, normalized_name, category, unit, current_quantity, reorder_level, created_by_id) "
                "VALUES (:i, :f, 'Hay', 'hay', 'FORAGE', 'KG', 0, 5, :u)"
            ), {"i": item_id, "f": farm_id, "u": user_id})
            connection.commit()
            with pytest.raises(IntegrityError):
                connection.execute(text(
                    "INSERT INTO feed_stock_movements "
                    "(id, farm_id, feed_item_id, client_request_id, movement_type, quantity, unit, resulting_quantity, reason, occurred_at, recorded_by_id) "
                    "VALUES (:id, :f, :i, :r, 'ADJUSTMENT_OUT', 1, 'KG', -1, 'invalid', now(), :u)"
                ), {"id": uuid.uuid4(), "f": farm_id, "i": item_id, "r": uuid.uuid4(), "u": user_id})
                connection.commit()
            connection.rollback()

            command.downgrade(config, "b7c9d2e4f601")
            assert not (FEED_TABLES & set(inspect(connection).get_table_names()))
            assert connection.scalar(text("SELECT count(*) FROM farms")) == 1
            connection.rollback()
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b3d5f7a9c210"
            assert compare_metadata(
                MigrationContext.configure(connection, opts={"compare_type": True}),
                Base.metadata,
            ) == []
            command.downgrade(config, "base")
    finally:
        if migration_engine is not None:
            migration_engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}", schema_name)
            assert schema_name != "icms_test_gui_20261017103146_ca6015f2"
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        admin_engine.dispose()
