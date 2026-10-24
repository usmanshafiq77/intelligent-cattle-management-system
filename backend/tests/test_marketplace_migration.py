import os, uuid
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
TABLES={"marketplace_listings","marketplace_listing_photos","marketplace_inquiries","marketplace_inquiry_messages","marketplace_favorites","marketplace_listing_status_history","marketplace_listing_reports","marketplace_moderation_actions","marketplace_sale_confirmations","marketplace_audit_events","marketplace_notifications"}

def test_marketplace_migration_isolated_upgrade_downgrade_reupgrade():
    url=os.environ["TEST_DATABASE_URL"]; admin=create_engine(url,pool_pre_ping=True); schema=f"icms_test_{uuid.uuid4().hex}"; engine=None; created=False
    try:
        with admin.begin() as connection:
            assert connection.scalar(text("SELECT current_database()"))=="icms_test"; assert schema!="icms_test_gui_20261017103146_ca6015f2"; connection.execute(text(f'CREATE SCHEMA "{schema}"')); created=True
        engine=create_engine(url,pool_pre_ping=True,connect_args={"options":f"-csearch_path={schema}"})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()"))==schema; connection.rollback(); config=Config(str(ROOT/"alembic.ini")); config.set_main_option("script_location",str(ROOT/"alembic")); config.attributes["connection"]=connection
            command.upgrade(config,"e0f2a3b4c905"); before=set(inspect(connection).get_table_names()); command.upgrade(config,"head")
            inspector=inspect(connection)
            assert connection.scalar(text("SELECT version_num FROM alembic_version"))=="b3d5f7a9c210"; assert TABLES<=set(inspector.get_table_names()); assert before<=set(inspector.get_table_names()); assert connection.scalar(text("SELECT count(*) FROM permissions WHERE code LIKE 'marketplace.%'"))==6
            assert {fk["name"] for fk in inspector.get_foreign_keys("marketplace_sale_confirmations")} >= {"fk_marketplace_sale_listing_scope","fk_marketplace_sale_finance_scope"}
            assert {fk["name"] for fk in inspector.get_foreign_keys("marketplace_inquiries")} >= {"fk_marketplace_inquiry_listing_scope"}
            assert {index["name"] for index in inspector.get_indexes("marketplace_listings")} >= {"uq_marketplace_active_cattle","ix_marketplace_browse"}
            assert compare_metadata(MigrationContext.configure(connection,opts={"compare_type":True}),Base.metadata)==[]
            command.downgrade(config,"e0f2a3b4c905"); assert not(TABLES&set(inspect(connection).get_table_names())); command.upgrade(config,"head"); assert TABLES<=set(inspect(connection).get_table_names())
    finally:
        if engine: engine.dispose()
        if created:
            with admin.begin() as connection: connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()
