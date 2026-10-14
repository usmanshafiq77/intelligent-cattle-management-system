import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.permissions import PERMISSION_CODES


pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_flexible_rbac_migration_lifecycle_and_tenant_constraint():
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

            command.upgrade(config, "b9f8ee48d20d")
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "b9f8ee48d20d"
            connection.rollback()

            command.upgrade(config, "c3a1f5e8d9b2")
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "c3a1f5e8d9b2"
            connection.rollback()

            command.upgrade(config, "d4b7c9e2a105")
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "d4b7c9e2a105"
            assert connection.scalar(
                text("SELECT count(*) FROM permissions")
            ) == len(PERMISSION_CODES)
            assert set(PERMISSION_CODES) == set(
                connection.scalars(text("SELECT code FROM permissions"))
            )

            table_names = set(inspect(connection).get_table_names())
            assert {
                "permissions",
                "farm_custom_roles",
                "farm_role_permissions",
                "farm_member_roles",
            } <= table_names

            user_a, user_b = uuid.uuid4(), uuid.uuid4()
            farm_a, farm_b = uuid.uuid4(), uuid.uuid4()
            member_b, role_a = uuid.uuid4(), uuid.uuid4()
            for user_id, suffix in ((user_a, "a"), (user_b, "b")):
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id, full_name, email, password_hash, "
                        "is_system_admin, status) VALUES "
                        "(:id, 'Migration User', :email, 'unused', false, "
                        "'ACTIVE')"
                    ),
                    {"id": user_id, "email": f"migration-{suffix}@example.com"},
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
                    "INSERT INTO farm_members "
                    "(id, farm_id, user_id, role, status) VALUES "
                    "(:id, :farm, :user, 'FARM_OWNER', 'ACTIVE')"
                ),
                {"id": member_b, "farm": farm_b, "user": user_b},
            )
            connection.execute(
                text(
                    "INSERT INTO farm_custom_roles (id, farm_id, name) "
                    "VALUES (:id, :farm, 'Farm A Role')"
                ),
                {"id": role_a, "farm": farm_a},
            )
            connection.commit()

            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO farm_member_roles "
                        "(member_id, role_id, farm_id) "
                        "VALUES (:member, :role, :farm)"
                    ),
                    {"member": member_b, "role": role_a, "farm": farm_b},
                )
                connection.commit()
            connection.rollback()

            command.downgrade(config, "c3a1f5e8d9b2")
            assert "farm_custom_roles" not in set(
                inspect(connection).get_table_names()
            )
            connection.rollback()
            command.upgrade(config, "head")
            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "d4b7c9e2a105"
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
