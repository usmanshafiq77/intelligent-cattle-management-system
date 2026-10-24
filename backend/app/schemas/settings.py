from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class FarmPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=32, pattern=r"^[+0-9() .-]*$")
    address: str | None = Field(default=None, max_length=500)
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    measurement_system: str = Field(default="METRIC", pattern=r"^(METRIC|IMPERIAL)$")
    milk_volume_unit: str = Field(default="LITER", pattern=r"^(LITER|GALLON)$")
    feed_weight_unit: str = Field(default="KG", pattern=r"^(KG|LB)$")
    notification_settings: dict[str, bool] = Field(default_factory=dict)
    operational_settings: dict[str, str | int | float | bool] = Field(default_factory=dict)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError: raise ValueError("Unknown IANA timezone") from None
        return value


class FarmPreferenceResponse(FarmPreferenceUpdate):
    farm_id: UUID
    updated_by_id: UUID
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
