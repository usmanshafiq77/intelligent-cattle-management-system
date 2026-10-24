
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
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
    FORGOT_PASSWORD_RATE_LIMIT_REQUESTS: int = Field(default=3, gt=0)
    FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=900, gt=0)
    RESET_PASSWORD_RATE_LIMIT_REQUESTS: int = Field(default=10, gt=0)
    RESET_PASSWORD_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=900, gt=0)
    RATE_LIMIT_MAX_KEYS: int = Field(default=10_000, gt=0)

    EMAIL_DELIVERY_MODE: str = "console"
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = Field(
        default=1440,
        gt=0,
    )
    FRONTEND_PUBLIC_URL: str = "http://localhost:8081"
    EMAIL_VERIFICATION_BASE_URL: str | None = None
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = Field(default=20, gt=0)
    PASSWORD_RESET_BASE_URL: str | None = None
    INVITATION_ACCEPT_BASE_URL: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int = Field(default=587, ge=1, le=65535)
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_USE_STARTTLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_SENDER_EMAIL: EmailStr | None = None
    SMTP_SENDER_NAME: str = "ICMS"
    SMTP_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, le=120)
    SMTP_MAX_ATTEMPTS: int = Field(default=3, ge=1, le=5)
    SMTP_RETRY_DELAY_SECONDS: float = Field(default=0.5, ge=0, le=30)
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "plain"
    MEDIA_ROOT: Path = BACKEND_DIR / "uploads"
    CATTLE_MEDIA_MAX_BYTES: int = Field(
        default=10 * 1024 * 1024,
        gt=0,
        le=10 * 1024 * 1024,
    )
    PROFILE_AVATAR_MAX_BYTES: int = Field(
        default=5 * 1024 * 1024,
        gt=0,
        le=5 * 1024 * 1024,
    )
    BACKUP_ROOT: Path = BACKEND_DIR / "backups" / "encrypted"
    BACKUP_ENCRYPTION_KEY: SecretStr | None = None
    BACKUP_KEY_ID: str = "primary"
    PG_DUMP_PATH: str = "pg_dump"
    PG_RESTORE_PATH: str = "pg_restore"
    GOOGLE_DRIVE_CLIENT_ID: str | None = None
    GOOGLE_DRIVE_CLIENT_SECRET: SecretStr | None = None
    GOOGLE_DRIVE_REDIRECT_URI: str = "http://localhost:8000/api/v1/admin/backups/google/callback"
    GOOGLE_DRIVE_OAUTH_SCOPES: str = "https://www.googleapis.com/auth/drive.file"
    GOOGLE_DRIVE_TIMEOUT_SECONDS: float = Field(default=30, gt=0, le=300)

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

    @field_validator(
        "FRONTEND_PUBLIC_URL",
        "EMAIL_VERIFICATION_BASE_URL",
        "PASSWORD_RESET_BASE_URL",
        "INVITATION_ACCEPT_BASE_URL",
        "GOOGLE_DRIVE_REDIRECT_URI",
    )
    @classmethod
    def validate_action_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if (
            not normalized
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "Public action URLs must be absolute HTTP(S) URLs without "
                "credentials, queries, or fragments"
            )
        return normalized

    @field_validator("EMAIL_DELIVERY_MODE")
    @classmethod
    def validate_email_mode(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"console", "memory", "smtp"}:
            raise ValueError("EMAIL_DELIVERY_MODE must be console, memory, or smtp")
        return normalized

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("LOG_LEVEL is invalid")
        return normalized

    @field_validator("LOG_FORMAT")
    @classmethod
    def validate_log_format(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"plain", "json"}:
            raise ValueError("LOG_FORMAT must be plain or json")
        return normalized

    @model_validator(mode="after")
    def validate_environment_security(self):
        environment = self.APP_ENV.strip().lower()
        secret = self.JWT_SECRET_KEY.get_secret_value()
        if environment not in {"development", "local"} and len(secret) < 32:
            raise ValueError("JWT_SECRET_KEY must contain at least 32 characters")

        if self.SMTP_USE_STARTTLS and self.SMTP_USE_SSL:
            raise ValueError("Choose SMTP_USE_STARTTLS or SMTP_USE_SSL, not both")

        if self.EMAIL_DELIVERY_MODE == "smtp":
            if not self.SMTP_HOST or not self.SMTP_SENDER_EMAIL:
                raise ValueError(
                    "SMTP_HOST and SMTP_SENDER_EMAIL are required in smtp mode"
                )
            if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
                raise ValueError(
                    "SMTP_USERNAME and SMTP_PASSWORD must be configured together"
                )
            if not self.SMTP_USE_STARTTLS and not self.SMTP_USE_SSL:
                raise ValueError(
                    "SMTP delivery requires STARTTLS or implicit SSL"
                )

        if environment == "production":
            if any(
                not origin.startswith("https://")
                for origin in self.CORS_ALLOWED_ORIGINS
            ):
                raise ValueError("Production CORS origins must use HTTPS")
            public_urls = [
                self.FRONTEND_PUBLIC_URL,
                self.EMAIL_VERIFICATION_BASE_URL,
                self.PASSWORD_RESET_BASE_URL,
                self.INVITATION_ACCEPT_BASE_URL,
            ]
            if any(url and not url.startswith("https://") for url in public_urls):
                raise ValueError("Production public action URLs must use HTTPS")
            if self.EMAIL_DELIVERY_MODE != "smtp":
                raise ValueError("Production requires EMAIL_DELIVERY_MODE=smtp")
            if secret in {
                "replace_with_a_long_random_secret",
                "change-me-change-me-change-me-change-me",
            }:
                raise ValueError("Production JWT_SECRET_KEY must not use a placeholder")
        return self

    @field_validator("BACKUP_KEY_ID")
    @classmethod
    def validate_backup_key_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError("BACKUP_KEY_ID must contain only letters, numbers, hyphens or underscores")
        return normalized

    @property
    def verification_action_url(self) -> str:
        return self.EMAIL_VERIFICATION_BASE_URL or (
            f"{self.FRONTEND_PUBLIC_URL}/auth/verify-email"
        )

    @property
    def password_reset_action_url(self) -> str:
        return self.PASSWORD_RESET_BASE_URL or (
            f"{self.FRONTEND_PUBLIC_URL}/reset-password"
        )

    @property
    def invitation_accept_action_url(self) -> str:
        return self.INVITATION_ACCEPT_BASE_URL or (
            f"{self.FRONTEND_PUBLIC_URL}/invitations/accept"
        )

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
