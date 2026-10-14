
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.farm_member import FarmRole, MemberStatus
from app.models.invitation import InvitationStatus


class InvitationCreate(BaseModel):
    email: EmailStr = Field(max_length=254)
    role: Literal[
        "FARM_MANAGER",
        "WORKER",
        "VETERINARIAN",
    ]


class InvitationResponse(BaseModel):
    id: UUID
    farm_id: UUID
    email: EmailStr
    role: FarmRole
    status: InvitationStatus
    expires_at: datetime
    created_at: datetime | None = None
    accepted_at: datetime | None = None

    # Present only in local development and automated tests.
    invitation_token: str | None = None


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=32, max_length=512)


class InvitationAcceptanceResponse(BaseModel):
    farm_id: UUID
    farm_name: str
    membership_id: UUID
    role: FarmRole
    membership_status: MemberStatus
    accepted_at: datetime
