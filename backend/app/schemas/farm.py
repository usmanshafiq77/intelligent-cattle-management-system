
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class FarmUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one farm field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Farm name cannot be null")
        return self

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


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
