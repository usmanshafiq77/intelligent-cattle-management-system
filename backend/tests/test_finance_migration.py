import os, re, uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa
from app.db.base import Base

pytestmark=pytest.mark.integration
ROOT=Path(__file__).resolve().parents[1]
TABLES={"finance_categories","financial_transactions","financial_adjustments","finance_payments","milk_sales","cattle_finance_transactions","finance_budgets","farm_assets","asset_maintenance_records","finance_audit_events","finance_attachments"}

def test_finance_migration_isolated_upgrade_downgrade_reupgrade():
    url=os.environ["TEST_DATABASE_URL"]; admin=create_engine(url,pool_pre_ping=True); schema=f"icms_test_{uuid.uuid4().hex}"; engine=None; created=False
    try:
        with admin.begin() as connection:
            assert connection.scalar(text("SELECT current_database()"))=="icms_test"
            assert schema!="icms_test_gui_20261017103146_ca6015f2"
            connection.execute(text(f'CREATE SCHEMA "{schema}"')); created=True
        engine=create_engine(url,pool_pre_ping=True,connect_args={"options":f"-csearch_path={schema}"})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()"))==schema; connection.rollback()
            config=Config(str(ROOT/"alembic.ini")); config.set_main_option("script_location",str(ROOT/"alembic")); config.attributes["connection"]=connection
            command.upgrade(config,"d9e1f2a3b804")
            user_id,farm_id=uuid.uuid4(),uuid.uuid4()
            connection.execute(text("INSERT INTO users (id,full_name,email,password_hash,is_system_admin,status,token_version) VALUES (:u,'Existing','finance-migration@example.com','x',false,'ACTIVE',0)"),{"u":user_id})
            connection.execute(text("INSERT INTO farms (id,name,owner_id) VALUES (:f,'Existing Farm',:u)"),{"f":farm_id,"u":user_id}); connection.commit()
            command.upgrade(config,"head")
            assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="b3d5f7a9c210"
            assert TABLES <= set(inspect(connection).get_table_names())
            assert connection.scalar(text("SELECT count(*) FROM farms"))==1
            assert connection.scalar(text("SELECT count(*) FROM permissions WHERE code LIKE 'finance.%'"))==10
            assert compare_metadata(MigrationContext.configure(connection,opts={"compare_type":True}),Base.metadata)==[]
            command.downgrade(config,"d9e1f2a3b804"); assert not(TABLES & set(inspect(connection).get_table_names()))
            assert connection.scalar(text("SELECT count(*) FROM farms"))==1
            command.upgrade(config,"head"); assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="b3d5f7a9c210"
            command.downgrade(config,"base")
    finally:
        if engine: engine.dispose()
        if created:
            assert re.fullmatch(r"icms_test_[0-9a-f]{32}",schema)
            with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
