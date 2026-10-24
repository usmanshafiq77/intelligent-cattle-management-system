import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


pytestmark = pytest.mark.integration
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_password_reset_migration_upgrade_and_rollback_preserve_core_data():
    database_url = os.environ["TEST_DATABASE_URL"]
    admin_engine = create_engine(database_url, pool_pre_ping=True)
    schema_name = f"icms_test_{uuid.uuid4().hex}"
    migration_engine = None
    created = False

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
            config = Config(str(BACKEND_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
            config.attributes["connection"] = connection

            command.upgrade(config, "a8b3c4d5e6f7")
            user_id = uuid.uuid4()
            farm_id = uuid.uuid4()
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, full_name, email, password_hash, is_system_admin, status) "
                    "VALUES (:id, 'Existing User', 'migration-existing@example.com', "
                    "'hash', false, 'ACTIVE')"
                ),
                {"id": user_id},
            )
            connection.execute(
                text(
                    "INSERT INTO farms (id, name, owner_id) "
                    "VALUES (:id, 'Existing Farm', :owner_id)"
                ),
                {"id": farm_id, "owner_id": user_id},
            )
            connection.commit()

            command.upgrade(config, "b7c9d2e4f601")
            inspector = inspect(connection)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b7c9d2e4f601"
            assert "password_reset_tokens" in inspector.get_table_names()
            assert "token_version" in {
                column["name"] for column in inspector.get_columns("users")
            }
            assert connection.scalar(
                text("SELECT token_version FROM users WHERE id=:id"),
                {"id": user_id},
            ) == 0
            assert connection.scalar(text("SELECT count(*) FROM users")) == 1
            assert connection.scalar(text("SELECT count(*) FROM farms")) == 1

            index_names = {
                index["name"]
                for index in inspector.get_indexes("password_reset_tokens")
            }
            assert "ix_password_reset_tokens_user_id" in index_names
            assert "uq_password_reset_tokens_one_active" in index_names
            foreign_keys = inspector.get_foreign_keys("password_reset_tokens")
            assert any(
                key["referred_table"] == "users"
                and key["options"].get("ondelete") == "CASCADE"
                for key in foreign_keys
            )

            command.downgrade(config, "a8b3c4d5e6f7")
            inspector = inspect(connection)
            assert "password_reset_tokens" not in inspector.get_table_names()
            assert "token_version" not in {
                column["name"] for column in inspector.get_columns("users")
            }
            assert connection.scalar(text("SELECT count(*) FROM users")) == 1
            assert connection.scalar(text("SELECT count(*) FROM farms")) == 1

            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "f1a3b5c7d906"
            command.downgrade(config, "base")
    finally:
        if migration_engine is not None:
            migration_engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}", schema_name)
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        admin_engine.dispose()
