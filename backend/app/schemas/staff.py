from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.farm_member import FarmRole, MemberStatus


class StaffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    user_id: UUID
    name: str
    email: str
    role: FarmRole
    status: MemberStatus
    joined_at: datetime
    custom_role_ids: list[UUID] = Field(default_factory=list)


class StaffRoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["FARM_MANAGER", "WORKER", "VETERINARIAN"]


class StaffStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ACTIVE", "INACTIVE"]


class CustomRoleAssignments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role_ids: list[UUID] = Field(min_length=1, max_length=50)


class EffectivePermissionsResponse(BaseModel):
    farm_id: UUID
    membership_id: UUID
    predefined_role: FarmRole
    custom_role_ids: list[UUID]
    permissions: list[str]
