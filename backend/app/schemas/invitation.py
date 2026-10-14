
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.farm_member import FarmRole
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

    # Development testing only
    invitation_token: str
