
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.user import UserStatus


class UserRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: UUID
    full_name: str
    email: EmailStr
    is_system_admin: bool
    status: UserStatus
    is_email_verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegistrationResponse(UserResponse):
    verification_delivery_status: Literal["SENT", "FAILED"]


class UserLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EmailVerificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)


class EmailVerificationResendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=254)


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=32, max_length=512)
    new_password: str = Field(min_length=12, max_length=128)


class MessageResponse(BaseModel):
    detail: str


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str = Field(min_length=2, max_length=150)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strength(cls, value):
        if not (any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value) and any(not c.isalnum() for c in value)):
            raise ValueError("Password must include upper-case, lower-case, numeric and symbol characters")
        return value


class EmailChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_email: EmailStr
    current_password: str = Field(min_length=1, max_length=128)


class ReauthenticateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=128)


class AccountDeletionCreate(ReauthenticateRequest):
    reason: str | None = Field(default=None, max_length=1000)


class UserPreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str | None = Field(default=None, max_length=32, pattern=r"^[+0-9() .-]*$")
    language: str = Field(default="en", pattern="^en$")
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    date_format: str = Field(default="YYYY-MM-DD", pattern=r"^(YYYY-MM-DD|DD/MM/YYYY|MM/DD/YYYY)$")
    time_format: str = Field(default="24H", pattern=r"^(12H|24H)$")
    theme: str = Field(default="emerald", pattern=r"^(emerald|midnight|indigo)$")

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try: ZoneInfo(value)
        except ZoneInfoNotFoundError: raise ValueError("Unknown IANA timezone") from None
        return value


class UserPreferenceResponse(UserPreferenceUpdate):
    user_id: UUID
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SecurityEventResponse(BaseModel):
    id: UUID
    event_type: str
    summary: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
