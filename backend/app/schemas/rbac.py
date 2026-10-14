from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.permissions import PERMISSION_CODES


def _clean_name(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) < 2:
        raise ValueError("Role name must contain at least 2 characters")
    return normalized


class CustomRoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] = Field(default_factory=list, max_length=100)

    _normalize_name = field_validator("name")(_clean_name)


class CustomRoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)


class CustomRoleResponse(BaseModel):
    id: UUID
    farm_id: UUID
    name: str
    description: str | None
    permissions: list[str]
    created_at: datetime


def validate_permission_codes(codes: list[str]) -> list[str]:
    unique_codes = sorted(set(codes))
    invalid = set(unique_codes) - PERMISSION_CODES
    if invalid:
        raise ValueError(
            "Unknown permission codes: " + ", ".join(sorted(invalid))
        )
    return unique_codes
