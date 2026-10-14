import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.rbac import FarmCustomRole, FarmMemberRole
from tests.helpers import authorization_header, create_owned_farm, create_user


pytestmark = pytest.mark.integration


def add_member(db, farm, user, role=FarmRole.WORKER):
    member = FarmMember(
        farm_id=farm.id,
        user_id=user.id,
        role=role,
        status=MemberStatus.ACTIVE,
    )
    db.add(member)
    db.commit()
    return member


def create_role(client, owner, farm, name="Finance Manager", permissions=None):
    return client.post(
        f"/api/v1/farms/{farm.id}/roles",
        headers=authorization_header(owner),
        json={
            "name": name,
            "description": "Farm-scoped role",
            "permissions": permissions or ["finance.view"],
        },
    )


def test_owner_can_create_list_view_and_update_custom_role(client, db_session):
    owner = create_user(db_session, email="rbac-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    created = create_role(client, owner, farm)
    assert created.status_code == 201
    role_id = created.json()["id"]
    assert created.json()["permissions"] == ["finance.view"]

    listed = client.get(
        f"/api/v1/farms/{farm.id}/roles",
        headers=authorization_header(owner),
    )
    assert listed.status_code == 200
    assert [role["id"] for role in listed.json()] == [role_id]

    viewed = client.get(
        f"/api/v1/farms/{farm.id}/roles/{role_id}",
        headers=authorization_header(owner),
    )
    assert viewed.status_code == 200

    updated = client.patch(
        f"/api/v1/farms/{farm.id}/roles/{role_id}",
        headers=authorization_header(owner),
        json={
            "name": "Payroll Lead",
            "description": None,
            "permissions": ["salary.manage", "salary.view"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Payroll Lead"
    assert updated.json()["description"] is None
    assert updated.json()["permissions"] == ["salary.manage", "salary.view"]


def test_custom_role_rejects_unknown_permission_and_rolls_back(client, db_session):
    owner = create_user(db_session, email="invalid-permission@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    created = create_role(client, owner, farm)
    role_id = created.json()["id"]

    response = client.patch(
        f"/api/v1/farms/{farm.id}/roles/{role_id}",
        headers=authorization_header(owner),
        json={"name": "Changed", "permissions": ["system.admin"]},
    )
    assert response.status_code == 422
    unchanged = client.get(
        f"/api/v1/farms/{farm.id}/roles/{role_id}",
        headers=authorization_header(owner),
    ).json()
    assert unchanged["name"] == "Finance Manager"
    assert unchanged["permissions"] == ["finance.view"]


def test_role_names_are_unique_per_farm_case_insensitively(client, db_session):
    owner = create_user(db_session, email="role-name-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    assert create_role(client, owner, farm, name="Feed Lead").status_code == 201
    duplicate = create_role(client, owner, farm, name="feed lead")
    assert duplicate.status_code == 409


def test_non_owner_cannot_manage_custom_roles_even_with_roles_permission(
    client, db_session
):
    owner = create_user(db_session, email="protected-owner@example.com")
    manager = create_user(db_session, email="protected-manager@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_member(db_session, farm, manager, FarmRole.FARM_MANAGER)
    role_id = create_role(
        client, owner, farm, permissions=["roles.manage"]
    ).json()["id"]
    assigned = client.post(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [role_id]},
    )
    assert assigned.status_code == 200
    denied = create_role(client, manager, farm, name="Escalated")
    assert denied.status_code == 403


def test_multiple_custom_roles_are_additive_and_removable(client, db_session):
    owner = create_user(db_session, email="multi-owner@example.com")
    worker = create_user(db_session, email="multi-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_member(db_session, farm, worker)
    finance_id = create_role(
        client, owner, farm, "Finance", ["finance.view"]
    ).json()["id"]
    reports_id = create_role(
        client, owner, farm, "Reports", ["reports.export"]
    ).json()["id"]

    assigned = client.post(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [finance_id, reports_id, finance_id]},
    )
    assert assigned.status_code == 200
    assert set(assigned.json()["custom_role_ids"]) == {finance_id, reports_id}

    effective = client.get(
        f"/api/v1/farms/{farm.id}/staff/permissions/me",
        headers=authorization_header(worker),
    )
    assert effective.status_code == 200
    permissions = set(effective.json()["permissions"])
    assert {"farm.view", "finance.view", "reports.export"} <= permissions

    removed = client.request(
        "DELETE",
        f"/api/v1/farms/{farm.id}/staff/{member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [finance_id]},
    )
    assert removed.status_code == 200
    assert removed.json()["custom_role_ids"] == [reports_id]


def test_inactive_member_has_no_effective_access(client, db_session):
    owner = create_user(db_session, email="inactive-rbac-owner@example.com")
    worker = create_user(db_session, email="inactive-rbac-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_member(db_session, farm, worker)
    role_id = create_role(client, owner, farm).json()["id"]
    client.post(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [role_id]},
    )
    client.patch(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/status",
        headers=authorization_header(owner),
        json={"status": "INACTIVE"},
    )
    response = client.get(
        f"/api/v1/farms/{farm.id}/staff/permissions/me",
        headers=authorization_header(worker),
    )
    assert response.status_code == 404


def test_cross_farm_role_assignment_is_rejected_by_api(client, db_session):
    owner_a = create_user(db_session, email="cross-role-a@example.com")
    owner_b = create_user(db_session, email="cross-role-b@example.com")
    worker = create_user(db_session, email="cross-role-worker@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="B")
    member = add_member(db_session, farm_a, worker)
    foreign_role = create_role(client, owner_b, farm_b).json()["id"]
    response = client.post(
        f"/api/v1/farms/{farm_a.id}/staff/{member.id}/roles",
        headers=authorization_header(owner_a),
        json={"role_ids": [foreign_role]},
    )
    assert response.status_code == 422


def test_cross_farm_role_assignment_is_rejected_by_database(db_session):
    owner_a = create_user(db_session, email="db-cross-a@example.com")
    owner_b = create_user(db_session, email="db-cross-b@example.com")
    worker = create_user(db_session, email="db-cross-worker@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="DB A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="DB B")
    member = add_member(db_session, farm_a, worker)
    role = FarmCustomRole(farm_id=farm_b.id, name="Foreign")
    db_session.add(role)
    db_session.commit()
    db_session.add(
        FarmMemberRole(
            member_id=member.id,
            role_id=role.id,
            farm_id=farm_a.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_assigned_role_cannot_be_deleted_until_removed(client, db_session):
    owner = create_user(db_session, email="delete-role-owner@example.com")
    worker = create_user(db_session, email="delete-role-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_member(db_session, farm, worker)
    role_id = create_role(client, owner, farm).json()["id"]
    client.post(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [role_id]},
    )
    blocked = client.delete(
        f"/api/v1/farms/{farm.id}/roles/{role_id}",
        headers=authorization_header(owner),
    )
    assert blocked.status_code == 409
    client.request(
        "DELETE",
        f"/api/v1/farms/{farm.id}/staff/{member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [role_id]},
    )
    deleted = client.delete(
        f"/api/v1/farms/{farm.id}/roles/{role_id}",
        headers=authorization_header(owner),
    )
    assert deleted.status_code == 204


def test_custom_roles_cannot_be_assigned_to_owner(client, db_session):
    owner = create_user(db_session, email="owner-escalation@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    owner_member = db_session.scalar(
        select(FarmMember).where(FarmMember.farm_id == farm.id)
    )
    role_id = create_role(client, owner, farm).json()["id"]
    response = client.post(
        f"/api/v1/farms/{farm.id}/staff/{owner_member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [role_id]},
    )
    assert response.status_code == 409


def test_unknown_role_id_does_not_partially_assign(client, db_session):
    owner = create_user(db_session, email="partial-owner@example.com")
    worker = create_user(db_session, email="partial-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_member(db_session, farm, worker)
    valid_id = create_role(client, owner, farm).json()["id"]
    response = client.post(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [valid_id, str(uuid.uuid4())]},
    )
    assert response.status_code == 422
    assert db_session.scalars(
        select(FarmMemberRole).where(FarmMemberRole.member_id == member.id)
    ).all() == []
