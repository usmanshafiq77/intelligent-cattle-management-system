import pytest
from pydantic import ValidationError

from app.core.migration_config import MigrationSettings


def test_alembic_environment_commits_target_validation_before_migrations():
    env_source = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "alembic"
        / "env.py"
    ).read_text(encoding="utf-8")

    validation_commit = env_source.index("connection.commit()")
    migration_configuration = env_source.index(
        "context.configure(",
        env_source.index("with connectable.connect() as connection:"),
    )
    assert validation_commit < migration_configuration


def test_migration_settings_ignore_unrelated_production_runtime_configuration():
    settings = MigrationSettings(
        _env_file=None,
        DB_NAME="migration_rehearsal",
        DB_PASSWORD="migration-only-password",
        APP_ENV="production",
        EMAIL_DELIVERY_MODE="console",
        FRONTEND_PUBLIC_URL="http://localhost:8081",
    )

    assert settings.DB_NAME == "migration_rehearsal"
    assert settings.DB_SCHEMA == "public"
    assert settings.DB_PASSWORD.get_secret_value() == "migration-only-password"


@pytest.mark.parametrize(
    "schema",
    ["public; DROP SCHEMA public", "two words", "public.other", 'bad"name'],
)
def test_migration_settings_reject_unsafe_schema_names(schema):
    with pytest.raises(ValidationError):
        MigrationSettings(
            _env_file=None,
            DB_PASSWORD="migration-only-password",
            DB_SCHEMA=schema,
        )
