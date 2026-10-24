
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FarmCreate(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=150
    )

    location: str | None = Field(
        default=None,
        max_length=255
    )

    description: str | None = Field(
        default=None,
        max_length=2000
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )


class FarmResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    location: str | None
    description: str | None
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )
