import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
SCHEMA_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MigrationSettings(BaseSettings):
    """Database-only settings for Alembic commands.

    Migration execution must not depend on web runtime concerns such as SMTP,
    public action URLs, CORS, or JWT configuration. Those remain mandatory when
    the FastAPI application loads its full Settings object.
    """

    DB_HOST: str = "localhost"
    DB_PORT: int = Field(default=5432, ge=1, le=65535)
    DB_NAME: str = "icms_db"
    DB_USER: str = "icms_app"
    DB_PASSWORD: SecretStr
    DB_SCHEMA: str = "public"

    @field_validator("DB_HOST", "DB_NAME", "DB_USER")
    @classmethod
    def require_nonempty_database_value(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Database connection values must not be empty")
        return normalized

    @field_validator("DB_SCHEMA")
    @classmethod
    def validate_schema_name(cls, value: str) -> str:
        normalized = value.strip()
        if not SCHEMA_NAME.fullmatch(normalized):
            raise ValueError("DB_SCHEMA must be a simple PostgreSQL identifier")
        return normalized

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_migration_settings() -> MigrationSettings:
    return MigrationSettings()
