
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserStatus


class UserRegister(BaseModel):
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

    
class UserLogin(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class EmailVerificationResendRequest(BaseModel):
    email: EmailStr = Field(max_length=254)


class MessageResponse(BaseModel):
    detail: str

