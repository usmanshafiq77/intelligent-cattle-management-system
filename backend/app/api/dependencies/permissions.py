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
            Permission.HEALTH_CREATE,
            Permission.HEALTH_DIAGNOSIS,
            Permission.HEALTH_VACCINATION_MANAGE,
            Permission.HEALTH_VACCINATION_ADMINISTER,
            Permission.HEALTH_TREATMENT_MANAGE,
            Permission.HEALTH_MEDICATION_ADMINISTER,
            Permission.HEALTH_VISIT_MANAGE,
            Permission.HEALTH_AUDIT_VIEW,
            Permission.MILK_VIEW,
            Permission.MILK_RECORD,
            Permission.MILK_MANAGE,
            Permission.MILK_LACTATION_MANAGE,
            Permission.MILK_QUALITY_MANAGE,
            Permission.MILK_CORRECT,
            Permission.MILK_ANALYTICS_VIEW,
            Permission.MILK_BULK_CREATE,
            Permission.FEED_VIEW,
            Permission.FEED_RECORD,
            Permission.FEED_MANAGE,
            Permission.BREEDING_VIEW,
            Permission.BREEDING_MANAGE,
            Permission.FINANCE_VIEW,
            Permission.FINANCE_MANAGE,
            Permission.MARKETPLACE_VIEW,
            Permission.MARKETPLACE_LISTING_MANAGE,
            Permission.MARKETPLACE_INQUIRY_MANAGE,
            Permission.MARKETPLACE_SALE_CONFIRM,
            Permission.MARKETPLACE_REPORT_CREATE,
            Permission.TASK_VIEW,
            Permission.TASK_MANAGE,
            Permission.CATTLE_ASSIGNMENT_MANAGE,
            Permission.NOTIFICATION_VIEW,
            Permission.REPORTS_VIEW,
            Permission.REPORTS_EXPORT,
        }
    ),
    FarmRole.WORKER: frozenset(
        {
            Permission.FARM_VIEW,
            Permission.CATTLE_VIEW,
            Permission.HEALTH_VIEW,
            Permission.HEALTH_CREATE,
            Permission.MILK_VIEW,
            Permission.MILK_RECORD,
            Permission.MILK_BULK_CREATE,
            Permission.FEED_VIEW,
            Permission.FEED_RECORD,
            Permission.BREEDING_VIEW,
            Permission.BREEDING_HEAT_RECORD,
            Permission.BREEDING_CALVING_RECORD,
            Permission.MARKETPLACE_VIEW,
            Permission.MARKETPLACE_REPORT_CREATE,
            Permission.TASK_VIEW,
            Permission.TASK_UPDATE_ASSIGNED,
            Permission.NOTIFICATION_VIEW,
        }
    ),
    FarmRole.VETERINARIAN: frozenset(
        {
            Permission.FARM_VIEW,
            Permission.CATTLE_VIEW,
            Permission.HEALTH_VIEW,
            Permission.HEALTH_MANAGE,
            Permission.HEALTH_CREATE,
            Permission.HEALTH_DIAGNOSIS,
            Permission.HEALTH_VACCINATION_MANAGE,
            Permission.HEALTH_VACCINATION_ADMINISTER,
            Permission.HEALTH_TREATMENT_MANAGE,
            Permission.HEALTH_MEDICATION_ADMINISTER,
            Permission.HEALTH_VISIT_MANAGE,
            Permission.HEALTH_AUDIT_VIEW,
            Permission.MILK_VIEW,
            Permission.MILK_ANALYTICS_VIEW,
            Permission.BREEDING_VIEW,
            Permission.BREEDING_PREGNANCY_ASSESS,
            Permission.BREEDING_REPORTS_VIEW,
            Permission.FEED_NUTRITION_VIEW,
            Permission.MARKETPLACE_VIEW,
            Permission.MARKETPLACE_REPORT_CREATE,
            Permission.TASK_VIEW,
            Permission.TASK_UPDATE_ASSIGNED,
            Permission.NOTIFICATION_VIEW,
        }
    ),
}

HEALTH_MANAGE_IMPLIED_PERMISSIONS = frozenset(
    {
        Permission.HEALTH_CREATE,
        Permission.HEALTH_DIAGNOSIS,
        Permission.HEALTH_VACCINATION_MANAGE,
        Permission.HEALTH_VACCINATION_ADMINISTER,
        Permission.HEALTH_TREATMENT_MANAGE,
        Permission.HEALTH_MEDICATION_ADMINISTER,
        Permission.HEALTH_VISIT_MANAGE,
        Permission.HEALTH_AUDIT_VIEW,
    }
)

MILK_MANAGE_IMPLIED_PERMISSIONS = frozenset(
    {
        Permission.MILK_LACTATION_MANAGE,
        Permission.MILK_QUALITY_MANAGE,
        Permission.MILK_CORRECT,
        Permission.MILK_ANALYTICS_VIEW,
        Permission.MILK_BULK_CREATE,
    }
)

FEED_MANAGE_IMPLIED_PERMISSIONS = frozenset(
    {
        Permission.FEED_RECORD,
        Permission.FEED_INVENTORY_MANAGE,
        Permission.FEED_SCHEDULE_MANAGE,
        Permission.FEED_NUTRITION_VIEW,
        Permission.FEED_NUTRITION_MANAGE,
        Permission.FEED_COST_VIEW,
        Permission.FEED_REPORTS_VIEW,
    }
)

BREEDING_MANAGE_IMPLIED_PERMISSIONS = frozenset(
    {
        Permission.BREEDING_HEAT_RECORD,
        Permission.BREEDING_EVENT_RECORD,
        Permission.BREEDING_CALVING_RECORD,
        Permission.BREEDING_PEDIGREE_MANAGE,
        Permission.BREEDING_REPORTS_VIEW,
    }
)

FINANCE_MANAGE_IMPLIED_PERMISSIONS = frozenset(
    {
        Permission.FINANCE_INCOME_MANAGE,
        Permission.FINANCE_EXPENSE_MANAGE,
        Permission.FINANCE_SALES_MANAGE,
        Permission.FINANCE_PAYMENTS_MANAGE,
        Permission.FINANCE_BUDGETS_MANAGE,
        Permission.FINANCE_ASSETS_MANAGE,
        Permission.FINANCE_REPORTS_VIEW,
        Permission.FINANCE_AUDIT_VIEW,
    }
)


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
    if Permission.HEALTH_MANAGE in permissions:
        permissions.update(HEALTH_MANAGE_IMPLIED_PERMISSIONS)
    if Permission.MILK_MANAGE in permissions:
        permissions.update(MILK_MANAGE_IMPLIED_PERMISSIONS)
    if Permission.FEED_MANAGE in permissions:
        permissions.update(FEED_MANAGE_IMPLIED_PERMISSIONS)
    if Permission.BREEDING_MANAGE in permissions:
        permissions.update(BREEDING_MANAGE_IMPLIED_PERMISSIONS)
    if Permission.FINANCE_MANAGE in permissions:
        permissions.update(FINANCE_MANAGE_IMPLIED_PERMISSIONS)
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


def require_veterinarian_permission(permission: Permission) -> Callable[..., FarmAccess]:
    """Require clinical permission and professional membership; owners cannot impersonate vets."""
    permission_dependency = require_farm_permission(permission)

    def dependency(access: FarmAccess = Depends(permission_dependency)) -> FarmAccess:
        if access.membership.role != FarmRole.VETERINARIAN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This clinical action requires an active Veterinarian membership",
            )
        return access

    return dependency
