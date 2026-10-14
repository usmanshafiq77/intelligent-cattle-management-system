from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess, require_farm_owner
from app.api.dependencies.permissions import (
    get_effective_permissions,
    require_farm_permission,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.rbac import FarmCustomRole, FarmMemberRole
from app.models.user import User
from app.schemas.staff import (
    CustomRoleAssignments,
    EffectivePermissionsResponse,
    StaffResponse,
    StaffRoleUpdate,
    StaffStatusUpdate,
)


router = APIRouter(
    prefix="/farms/{farm_id}/staff",
    tags=["Staff Management"],
)


def _custom_role_ids(
    db: Session, *, farm_id: UUID, membership_id: UUID
) -> list[UUID]:
    return list(
        db.scalars(
            select(FarmMemberRole.role_id)
            .where(
                FarmMemberRole.farm_id == farm_id,
                FarmMemberRole.member_id == membership_id,
            )
            .order_by(FarmMemberRole.role_id)
        )
    )


def _staff_response(
    db: Session, member: FarmMember, user: User
) -> StaffResponse:
    return StaffResponse(
        membership_id=member.id,
        user_id=user.id,
        name=user.full_name,
        email=user.email,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
        custom_role_ids=_custom_role_ids(
            db, farm_id=member.farm_id, membership_id=member.id
        ),
    )


def _target_staff(
    db: Session,
    *,
    farm_id: UUID,
    membership_id: UUID,
    lock: bool = False,
) -> tuple[FarmMember, User]:
    statement = (
        select(FarmMember, User)
        .join(User, User.id == FarmMember.user_id)
        .where(
            FarmMember.id == membership_id,
            FarmMember.farm_id == farm_id,
        )
    )
    if lock:
        statement = statement.with_for_update()
    record = db.execute(statement).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff member not found",
        )
    return record


@router.get("", response_model=list[StaffResponse])
def list_farm_staff(
    farm_id: UUID,
    member_status: MemberStatus | None = Query(default=None, alias="status"),
    role: FarmRole | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.STAFF_VIEW)
    ),
    db: Session = Depends(get_db),
):
    statement = (
        select(FarmMember, User)
        .join(User, User.id == FarmMember.user_id)
        .where(FarmMember.farm_id == farm_id)
    )
    if member_status is not None:
        statement = statement.where(FarmMember.status == member_status)
    if role is not None:
        statement = statement.where(FarmMember.role == role)
    records = db.execute(
        statement.order_by(FarmMember.joined_at.desc(), FarmMember.id)
        .limit(limit)
        .offset(offset)
    ).all()
    return [_staff_response(db, member, user) for member, user in records]


@router.get(
    "/permissions/me", response_model=EffectivePermissionsResponse
)
def get_my_effective_permissions(
    farm_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.FARM_VIEW)
    ),
    db: Session = Depends(get_db),
):
    permissions = get_effective_permissions(db, access)
    return EffectivePermissionsResponse(
        farm_id=farm_id,
        membership_id=access.membership.id,
        predefined_role=access.membership.role,
        custom_role_ids=_custom_role_ids(
            db,
            farm_id=farm_id,
            membership_id=access.membership.id,
        ),
        permissions=sorted(permission.value for permission in permissions),
    )


@router.get("/{membership_id}", response_model=StaffResponse)
def get_staff_details(
    farm_id: UUID,
    membership_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.STAFF_VIEW)
    ),
    db: Session = Depends(get_db),
):
    member, user = _target_staff(
        db, farm_id=farm_id, membership_id=membership_id
    )
    return _staff_response(db, member, user)


@router.patch("/{membership_id}/role", response_model=StaffResponse)
def change_staff_role(
    farm_id: UUID,
    membership_id: UUID,
    data: StaffRoleUpdate,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    member, user = _target_staff(
        db, farm_id=farm_id, membership_id=membership_id, lock=True
    )
    if (
        member.role == FarmRole.FARM_OWNER
        or member.user_id == owner_access.farm.owner_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The authoritative owner role cannot be changed",
        )
    member.role = FarmRole(data.role)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not change staff role",
        ) from None
    return _staff_response(db, member, user)


@router.patch("/{membership_id}/status", response_model=StaffResponse)
def change_staff_status(
    farm_id: UUID,
    membership_id: UUID,
    data: StaffStatusUpdate,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    member, user = _target_staff(
        db, farm_id=farm_id, membership_id=membership_id, lock=True
    )
    if (
        member.role == FarmRole.FARM_OWNER
        or member.user_id == owner_access.farm.owner_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The authoritative owner cannot be deactivated",
        )
    member.status = MemberStatus(data.status)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not change staff status",
        ) from None
    return _staff_response(db, member, user)


def _validated_roles(
    db: Session, *, farm_id: UUID, role_ids: list[UUID]
) -> list[FarmCustomRole]:
    unique_ids = set(role_ids)
    roles = list(
        db.scalars(
            select(FarmCustomRole).where(
                FarmCustomRole.farm_id == farm_id,
                FarmCustomRole.id.in_(unique_ids),
            )
        )
    )
    if len(roles) != len(unique_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="One or more custom roles do not belong to this farm",
        )
    return roles


@router.post(
    "/{membership_id}/roles",
    response_model=StaffResponse,
    status_code=status.HTTP_200_OK,
)
def assign_custom_roles(
    farm_id: UUID,
    membership_id: UUID,
    data: CustomRoleAssignments,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    member, user = _target_staff(
        db, farm_id=farm_id, membership_id=membership_id, lock=True
    )
    if member.role == FarmRole.FARM_OWNER:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Custom roles cannot be assigned to the farm owner",
        )
    roles = _validated_roles(db, farm_id=farm_id, role_ids=data.role_ids)
    existing = set(
        db.scalars(
            select(FarmMemberRole.role_id).where(
                FarmMemberRole.member_id == member.id,
                FarmMemberRole.farm_id == farm_id,
            )
        )
    )
    for role in roles:
        if role.id not in existing:
            db.add(
                FarmMemberRole(
                    member_id=member.id,
                    role_id=role.id,
                    farm_id=farm_id,
                )
            )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Custom role assignment conflicts with farm state",
        ) from None
    return _staff_response(db, member, user)


@router.delete("/{membership_id}/roles", response_model=StaffResponse)
def remove_custom_roles(
    farm_id: UUID,
    membership_id: UUID,
    data: CustomRoleAssignments,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    member, user = _target_staff(
        db, farm_id=farm_id, membership_id=membership_id, lock=True
    )
    _validated_roles(db, farm_id=farm_id, role_ids=data.role_ids)
    assignments = list(
        db.scalars(
            select(FarmMemberRole).where(
                FarmMemberRole.member_id == member.id,
                FarmMemberRole.farm_id == farm_id,
                FarmMemberRole.role_id.in_(set(data.role_ids)),
            )
        )
    )
    for assignment in assignments:
        db.delete(assignment)
    db.commit()
    return _staff_response(db, member, user)
