
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_ENV: str = "development"

    CORS_ALLOWED_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:8081",
            "http://127.0.0.1:8081",
        ]
    )

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
    MEDIA_ROOT: Path = BACKEND_DIR / "uploads"
    CATTLE_MEDIA_MAX_BYTES: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        le=10 * 1024 * 1024,
    )

    @field_validator("CORS_ALLOWED_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        normalized: list[str] = []
        for origin in origins:
            value = origin.strip().rstrip("/")
            parsed = urlsplit(value)
            if (
                not value
                or value == "*"
                or parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError(
                    "CORS origins must be explicit HTTP(S) origins without "
                    "credentials, paths, queries, fragments, or wildcards"
                )
            if value not in normalized:
                normalized.append(value)
        return normalized

    @model_validator(mode="after")
    def require_secure_production_cors(self):
        if self.APP_ENV.lower() == "production" and any(
            not origin.startswith("https://")
            for origin in self.CORS_ALLOWED_ORIGINS
        ):
            raise ValueError("Production CORS origins must use HTTPS")
        return self

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
