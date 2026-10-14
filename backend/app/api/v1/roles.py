from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess, require_farm_owner
from app.db.session import get_db
from app.models.rbac import (
    FarmCustomRole,
    FarmMemberRole,
    FarmRolePermission,
)
from app.schemas.rbac import (
    CustomRoleCreate,
    CustomRoleResponse,
    CustomRoleUpdate,
    validate_permission_codes,
)


router = APIRouter(
    prefix="/farms/{farm_id}/roles",
    tags=["Farm Custom Roles"],
)


def _permission_codes(db: Session, role_id: UUID) -> list[str]:
    return list(
        db.scalars(
            select(FarmRolePermission.permission_code)
            .where(FarmRolePermission.role_id == role_id)
            .order_by(FarmRolePermission.permission_code)
        )
    )


def _response(db: Session, role: FarmCustomRole) -> CustomRoleResponse:
    return CustomRoleResponse(
        id=role.id,
        farm_id=role.farm_id,
        name=role.name,
        description=role.description,
        permissions=_permission_codes(db, role.id),
        created_at=role.created_at,
    )


def _role_or_404(
    db: Session, *, farm_id: UUID, role_id: UUID, lock: bool = False
) -> FarmCustomRole:
    statement = select(FarmCustomRole).where(
        FarmCustomRole.id == role_id,
        FarmCustomRole.farm_id == farm_id,
    )
    if lock:
        statement = statement.with_for_update()
    role = db.scalar(statement)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Custom role not found",
        )
    return role


def _validated_permissions(codes: list[str]) -> list[str]:
    try:
        return validate_permission_codes(codes)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None


def _set_permissions(
    db: Session, *, role_id: UUID, codes: list[str]
) -> None:
    existing = list(
        db.scalars(
            select(FarmRolePermission).where(
                FarmRolePermission.role_id == role_id
            )
        )
    )
    for permission in existing:
        db.delete(permission)
    db.flush()
    for code in codes:
        db.add(
            FarmRolePermission(role_id=role_id, permission_code=code)
        )


@router.post(
    "",
    response_model=CustomRoleResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_custom_role(
    farm_id: UUID,
    data: CustomRoleCreate,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    codes = _validated_permissions(data.permissions)
    duplicate = db.scalar(
        select(FarmCustomRole.id).where(
            FarmCustomRole.farm_id == farm_id,
            func.lower(FarmCustomRole.name) == data.name.lower(),
        )
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A custom role with this name already exists",
        )
    role = FarmCustomRole(
        farm_id=farm_id,
        name=data.name,
        description=data.description,
    )
    try:
        db.add(role)
        db.flush()
        _set_permissions(db, role_id=role.id, codes=codes)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Custom role conflicts with current farm state",
        ) from None
    db.refresh(role)
    return _response(db, role)


@router.get("", response_model=list[CustomRoleResponse])
def list_custom_roles(
    farm_id: UUID,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    roles = db.scalars(
        select(FarmCustomRole)
        .where(FarmCustomRole.farm_id == farm_id)
        .order_by(func.lower(FarmCustomRole.name), FarmCustomRole.id)
    )
    return [_response(db, role) for role in roles]


@router.get("/{role_id}", response_model=CustomRoleResponse)
def get_custom_role(
    farm_id: UUID,
    role_id: UUID,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    return _response(
        db, _role_or_404(db, farm_id=farm_id, role_id=role_id)
    )


@router.patch("/{role_id}", response_model=CustomRoleResponse)
def update_custom_role(
    farm_id: UUID,
    role_id: UUID,
    data: CustomRoleUpdate,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    role = _role_or_404(db, farm_id=farm_id, role_id=role_id, lock=True)
    permission_codes = (
        _validated_permissions(data.permissions)
        if data.permissions is not None
        else None
    )
    if data.name is not None and data.name.lower() != role.name.lower():
        duplicate = db.scalar(
            select(FarmCustomRole.id).where(
                FarmCustomRole.farm_id == farm_id,
                func.lower(FarmCustomRole.name) == data.name.lower(),
                FarmCustomRole.id != role.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A custom role with this name already exists",
            )
        role.name = data.name
    if "description" in data.model_fields_set:
        role.description = data.description
    if permission_codes is not None:
        _set_permissions(
            db,
            role_id=role.id,
            codes=permission_codes,
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Custom role conflicts with current farm state",
        ) from None
    db.refresh(role)
    return _response(db, role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_custom_role(
    farm_id: UUID,
    role_id: UUID,
    owner_access: FarmAccess = Depends(require_farm_owner),
    db: Session = Depends(get_db),
):
    role = _role_or_404(db, farm_id=farm_id, role_id=role_id, lock=True)
    assigned = db.scalar(
        select(FarmMemberRole.member_id)
        .where(FarmMemberRole.role_id == role.id)
        .limit(1)
    )
    if assigned is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assigned custom roles must be removed before deletion",
        )
    db.delete(role)
    db.commit()
    return None
