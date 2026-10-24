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
ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "user_preferences", "pending_email_changes", "security_events",
    "account_deletion_requests", "farm_preferences", "google_drive_credentials",
    "backup_configuration", "backup_jobs", "restore_verifications",
}


def test_settings_backup_migration_upgrade_downgrade_reapply_and_preserve_data():
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
            command.upgrade(config, "f1a3b5c7d906")
            user_id = uuid.uuid4()
            connection.execute(text("INSERT INTO users (id,full_name,email,password_hash,is_system_admin,status,token_version) VALUES (:id,'Preserved User','settings-migration@example.com','x',false,'ACTIVE',0)"), {"id": user_id})
            connection.commit()

            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b3d5f7a9c210"
            assert TABLES <= set(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT count(*) FROM users WHERE id=:id"), {"id": user_id}) == 1
            checks = {item["name"] for item in inspect(connection).get_check_constraints("backup_jobs")}
            assert {"ck_backup_job_type", "ck_backup_job_status", "ck_backup_job_attempts"} <= checks
            with pytest.raises(IntegrityError):
                connection.execute(text("INSERT INTO backup_jobs (id,request_id,backup_type,status) VALUES (:id,:request,'INVALID','PENDING')"), {"id": uuid.uuid4(), "request": uuid.uuid4()})
            connection.rollback()

            command.downgrade(config, "a2c4e6f8b108")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "a2c4e6f8b108"
            assert not (TABLES & set(inspect(connection).get_table_names()))
            assert "operational_tasks" in inspect(connection).get_table_names()
            assert connection.scalar(text("SELECT count(*) FROM users WHERE id=:id"), {"id": user_id}) == 1

            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "b3d5f7a9c210"
            assert compare_metadata(MigrationContext.configure(connection, opts={"compare_type": True}), Base.metadata) == []
    finally:
        if engine: engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}", schema)
            with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
