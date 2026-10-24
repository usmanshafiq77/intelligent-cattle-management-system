from alembic.config import Config
from alembic.script import ScriptDirectory

import app.models  # noqa: F401
from app.db.base import Base
from app.core.migrations import EXPECTED_DATABASE_REVISION


EXPECTED_TABLES = {
    "breeds",
    "breeding_audit_events",
    "breeding_events",
    "breeding_reminders",
    "calving_events",
    "calving_offspring",
    "cattle",
    "cattle_lifecycle_events",
    "cattle_media",
    "cattle_weight_records",
    "email_verification_tokens",
    "feed_consumption_records",
    "feed_items",
    "feed_stock_movements",
    "feeding_schedules",
    "farm_custom_roles",
    "farm_member_roles",
    "farm_members",
    "farm_role_permissions",
    "farms",
    "finance_audit_events",
    "finance_attachments",
    "finance_budgets",
    "finance_categories",
    "finance_payments",
    "financial_adjustments",
    "financial_transactions",
    "farm_assets",
    "asset_maintenance_records",
    "milk_sales",
    "cattle_finance_transactions",
    "health_diagnoses",
    "health_encounters",
    "health_record_corrections",
    "invitations",
    "heat_observations",
    "medication_administrations",
    "milk_lactations",
    "milk_quality_measurements",
    "milk_record_corrections",
    "milking_sessions",
    "password_reset_tokens",
    "parentage_verifications",
    "pregnancy_examinations",
    "pregnancy_losses",
    "nutrition_plan_items",
    "nutrition_plans",
    "permissions",
    "treatment_plans",
    "users",
    "vaccination_administrations",
    "vaccination_schedules",
    "veterinary_visits",
    "marketplace_audit_events",
    "marketplace_favorites",
    "marketplace_inquiries",
    "marketplace_inquiry_messages",
    "marketplace_listing_photos",
    "marketplace_listing_reports",
    "marketplace_listing_status_history",
    "marketplace_listings",
    "marketplace_moderation_actions",
    "marketplace_notifications",
    "marketplace_sale_confirmations",
}

EXPECTED_REVISIONS = [
    "b9f8ee48d20d",
    "c3a1f5e8d9b2",
    "d4b7c9e2a105",
    "e6f1a2b3c4d5",
    "f7a2b3c4d5e6",
    "a8b3c4d5e6f7",
    "b7c9d2e4f601",
    "c8d0e1f2a703",
    "d9e1f2a3b804",
    "e0f2a3b4c905",
    "f1a3b5c7d906",
]


def test_sqlalchemy_table_contract_is_reviewed():
    actual = set(Base.metadata.tables)
    assert actual == EXPECTED_TABLES, (
        f"SQLAlchemy table contract changed; missing={sorted(EXPECTED_TABLES - actual)}, "
        f"unexpected={sorted(actual - EXPECTED_TABLES)}"
    )


def test_alembic_chain_and_head_are_reviewed():
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)
    revisions = [
        revision.revision
        for revision in reversed(list(script.walk_revisions()))
    ]
    assert revisions == EXPECTED_REVISIONS
    assert script.get_heads() == [EXPECTED_REVISIONS[-1]]
    assert EXPECTED_DATABASE_REVISION == EXPECTED_REVISIONS[-1]
