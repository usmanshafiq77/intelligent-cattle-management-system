
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_ENV: str = "development"

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "icms_db"
    DB_USER: str = "icms_app"
    DB_PASSWORD: SecretStr

    JWT_SECRET_KEY: SecretStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        gt=0,
    )

    AUTH_RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT_REQUESTS: int = Field(default=5, gt=0)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, gt=0)
    REGISTER_RATE_LIMIT_REQUESTS: int = Field(default=3, gt=0)
    REGISTER_RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=3600,
        gt=0,
    )
    VERIFICATION_RESEND_RATE_LIMIT_REQUESTS: int = Field(
        default=3,
        gt=0,
    )
    VERIFICATION_RESEND_RATE_LIMIT_WINDOW_SECONDS: int = Field(
        default=3600,
        gt=0,
    )
    RATE_LIMIT_MAX_KEYS: int = Field(default=10_000, gt=0)

    EMAIL_DELIVERY_MODE: str = "console"
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,
        gt=0,
    )
    EMAIL_VERIFICATION_BASE_URL: str = (
        "http://localhost:8765/api/v1/auth/verify-email"
    )

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
