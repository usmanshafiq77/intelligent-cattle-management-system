from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import (
    FarmAccess,
    require_active_farm_member,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.farm_member import FarmRole, MemberStatus
from app.models.rbac import FarmMemberRole, FarmRolePermission


PREDEFINED_ROLE_PERMISSIONS: dict[FarmRole, frozenset[Permission]] = {
    FarmRole.FARM_MANAGER: frozenset(
        {
            Permission.FARM_VIEW,
            Permission.STAFF_VIEW,
            Permission.CATTLE_VIEW,
            Permission.CATTLE_CREATE,
            Permission.CATTLE_UPDATE,
            Permission.HEALTH_VIEW,
            Permission.HEALTH_MANAGE,
            Permission.MILK_VIEW,
            Permission.MILK_RECORD,
            Permission.MILK_MANAGE,
            Permission.FEED_VIEW,
            Permission.FEED_MANAGE,
            Permission.BREEDING_VIEW,
            Permission.BREEDING_MANAGE,
            Permission.REPORTS_VIEW,
            Permission.REPORTS_EXPORT,
        }
    ),
    FarmRole.WORKER: frozenset(
        {
            Permission.FARM_VIEW,
            Permission.CATTLE_VIEW,
            Permission.HEALTH_VIEW,
            Permission.MILK_VIEW,
            Permission.MILK_RECORD,
            Permission.FEED_VIEW,
        }
    ),
    FarmRole.VETERINARIAN: frozenset(
        {
            Permission.FARM_VIEW,
            Permission.CATTLE_VIEW,
            Permission.HEALTH_VIEW,
            Permission.HEALTH_MANAGE,
            Permission.BREEDING_VIEW,
        }
    ),
}


def get_effective_permissions(
    db: Session,
    access: FarmAccess,
) -> frozenset[Permission]:
    membership = access.membership
    if membership.status != MemberStatus.ACTIVE:
        return frozenset()

    if membership.role == FarmRole.FARM_OWNER:
        if access.farm.owner_id != membership.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Farm ownership mismatch",
            )
        return frozenset(Permission)

    permissions = set(
        PREDEFINED_ROLE_PERMISSIONS.get(membership.role, frozenset())
    )
    custom_codes = db.scalars(
        select(FarmRolePermission.permission_code)
        .join(
            FarmMemberRole,
            FarmMemberRole.role_id == FarmRolePermission.role_id,
        )
        .where(
            FarmMemberRole.member_id == membership.id,
            FarmMemberRole.farm_id == access.farm.id,
        )
    )
    permissions.update(Permission(code) for code in custom_codes)
    return frozenset(permissions)


def require_farm_permission(
    permission: Permission,
) -> Callable[..., FarmAccess]:
    def dependency(
        access: FarmAccess = Depends(require_active_farm_member),
        db: Session = Depends(get_db),
    ) -> FarmAccess:
        if permission not in get_effective_permissions(db, access):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission.value}",
            )
        return access

    return dependency
