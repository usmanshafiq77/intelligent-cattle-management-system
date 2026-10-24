
import os
import re
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.core.permissions import PERMISSION_CODES


pytestmark = pytest.mark.integration

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# Permissions introduced by Step 17.
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

# Permissions introduced by Step 18.
STEP_18_MILK_PERMISSIONS = {
    "milk.lactation.manage",
    "milk.quality.manage",
    "milk.bulk.create",
    "milk.correct",
    "milk.analytics.view",
}

# Permissions introduced by the feed migration after Step 18.
FEED_MIGRATION_PERMISSIONS = {
    "feed.record",
    "feed.inventory.manage",
    "feed.schedule.manage",
    "feed.nutrition.view",
    "feed.nutrition.manage",
    "feed.cost.view",
    "feed.reports.view",
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

# Exact permission catalog expected at the RBAC migration revision.
STEP_16_PERMISSION_CODES = (
    set(PERMISSION_CODES)
    - STEP_17_HEALTH_PERMISSIONS
    - STEP_18_MILK_PERMISSIONS
    - FEED_MIGRATION_PERMISSIONS
    - BREEDING_MIGRATION_PERMISSIONS
    - FINANCE_MIGRATION_PERMISSIONS
    - MARKETPLACE_MIGRATION_PERMISSIONS
)


def test_flexible_rbac_migration_lifecycle_and_tenant_constraint():
    database_url = os.environ["TEST_DATABASE_URL"]

    # Never run this test against the application database.
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
        # Create a unique disposable schema.
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

            # Initial database revision.
            command.upgrade(config, "b9f8ee48d20d")

            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "b9f8ee48d20d"

            connection.rollback()

            # Security foundation revision.
            command.upgrade(config, "c3a1f5e8d9b2")

            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "c3a1f5e8d9b2"

            connection.rollback()

            # Flexible RBAC revision.
            command.upgrade(config, "d4b7c9e2a105")

            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "d4b7c9e2a105"

            # Only the original 24 permission codes should exist.
            actual_permissions = set(
                connection.scalars(
                    text("SELECT code FROM permissions")
                )
            )

            assert len(STEP_16_PERMISSION_CODES) == 24
            assert len(actual_permissions) == 24
            assert actual_permissions == STEP_16_PERMISSION_CODES

            table_names = set(
                inspect(connection).get_table_names()
            )

            assert {
                "permissions",
                "farm_custom_roles",
                "farm_role_permissions",
                "farm_member_roles",
            } <= table_names

            # Create two independent farms.
            user_a, user_b = uuid.uuid4(), uuid.uuid4()
            farm_a, farm_b = uuid.uuid4(), uuid.uuid4()
            member_b, role_a = uuid.uuid4(), uuid.uuid4()

            for user_id, suffix in (
                (user_a, "a"),
                (user_b, "b"),
            ):
                connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id, full_name, email, password_hash, "
                        "is_system_admin, status) "
                        "VALUES "
                        "(:id, 'Migration User', :email, "
                        "'unused', false, 'ACTIVE')"
                    ),
                    {
                        "id": user_id,
                        "email": f"migration-{suffix}@example.com",
                    },
                )

            connection.execute(
                text(
                    "INSERT INTO farms (id, name, owner_id) "
                    "VALUES "
                    "(:a, 'A', :user_a), "
                    "(:b, 'B', :user_b)"
                ),
                {
                    "a": farm_a,
                    "b": farm_b,
                    "user_a": user_a,
                    "user_b": user_b,
                },
            )

            connection.execute(
                text(
                    "INSERT INTO farm_members "
                    "(id, farm_id, user_id, role, status) "
                    "VALUES "
                    "(:id, :farm, :user, 'FARM_OWNER', 'ACTIVE')"
                ),
                {
                    "id": member_b,
                    "farm": farm_b,
                    "user": user_b,
                },
            )

            connection.execute(
                text(
                    "INSERT INTO farm_custom_roles "
                    "(id, farm_id, name) "
                    "VALUES (:id, :farm, 'Farm A Role')"
                ),
                {
                    "id": role_a,
                    "farm": farm_a,
                },
            )

            connection.commit()

            # Cross-farm membership-to-role assignment must fail.
            with pytest.raises(IntegrityError):
                connection.execute(
                    text(
                        "INSERT INTO farm_member_roles "
                        "(member_id, role_id, farm_id) "
                        "VALUES (:member, :role, :farm)"
                    ),
                    {
                        "member": member_b,
                        "role": role_a,
                        "farm": farm_b,
                    },
                )
                connection.commit()

            connection.rollback()

            # Verify RBAC migration downgrade.
            command.downgrade(config, "c3a1f5e8d9b2")

            assert "farm_custom_roles" not in set(
                inspect(connection).get_table_names()
            )

            connection.rollback()

            # Verify RBAC migration can be reapplied.
            command.upgrade(config, "d4b7c9e2a105")

            assert connection.scalar(
                text("SELECT version_num FROM alembic_version")
            ) == "d4b7c9e2a105"

            assert set(
                connection.scalars(
                    text("SELECT code FROM permissions")
                )
            ) == STEP_16_PERMISSION_CODES

            connection.rollback()

            # Clean up migration objects in the disposable schema.
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
