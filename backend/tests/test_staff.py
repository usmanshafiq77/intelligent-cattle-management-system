
import pytest

from app.models.farm_member import (
    FarmMember,
    FarmRole,
    MemberStatus,
)
from tests.helpers import (
    authorization_header,
    create_owned_farm,
    create_user,
)


pytestmark = pytest.mark.integration


def add_staff(db, farm, user, role, status=MemberStatus.ACTIVE):
    member = FarmMember(
        farm_id=farm.id,
        user_id=user.id,
        role=role,
        status=status,
    )
    db.add(member)
    db.commit()
    return member


def test_owner_can_list_farm_staff(client, db_session):
    owner = create_user(db_session, email="staff-owner@example.com")
    worker = create_user(db_session, email="staff-worker@example.com")

    farm = create_owned_farm(db_session, owner=owner)
    add_staff(db_session, farm, worker, FarmRole.WORKER)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff",
        headers=authorization_header(owner),
    )

    assert response.status_code == 200

    members = response.json()
    assert len(members) == 2

    assert {member["role"] for member in members} == {
        "FARM_OWNER",
        "WORKER",
    }

    assert all("password_hash" not in member for member in members)


def test_manager_can_list_staff(client, db_session):
    owner = create_user(db_session, email="manager-owner@example.com")
    manager = create_user(db_session, email="manager-user@example.com")

    farm = create_owned_farm(db_session, owner=owner)
    add_staff(db_session, farm, manager, FarmRole.FARM_MANAGER)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff",
        headers=authorization_header(manager),
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.parametrize(
    "role",
    [FarmRole.WORKER, FarmRole.VETERINARIAN],
)
def test_restricted_roles_cannot_list_staff(
    client, db_session, role
):
    owner = create_user(db_session, email="restricted-owner@example.com")
    employee = create_user(
        db_session,
        email=f"{role.value.lower()}@example.com",
    )

    farm = create_owned_farm(db_session, owner=owner)
    add_staff(db_session, farm, employee, role)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff",
        headers=authorization_header(employee),
    )

    assert response.status_code == 403


def test_non_member_cannot_list_staff(client, db_session):
    owner = create_user(db_session, email="nonmember-owner@example.com")
    outsider = create_user(db_session, email="outsider@example.com")
    farm = create_owned_farm(db_session, owner=owner)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff",
        headers=authorization_header(outsider),
    )

    assert response.status_code == 404


def test_inactive_member_cannot_list_staff(client, db_session):
    owner = create_user(db_session, email="inactive-owner@example.com")
    manager = create_user(db_session, email="inactive-manager@example.com")

    farm = create_owned_farm(db_session, owner=owner)
    add_staff(
        db_session,
        farm,
        manager,
        FarmRole.FARM_MANAGER,
        MemberStatus.INACTIVE,
    )

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff",
        headers=authorization_header(manager),
    )

    assert response.status_code == 404


def test_staff_list_is_isolated_between_farms(client, db_session):
    owner_a = create_user(db_session, email="isolation-owner-a@example.com")
    owner_b = create_user(db_session, email="isolation-owner-b@example.com")
    worker_a = create_user(db_session, email="isolation-worker-a@example.com")
    worker_b = create_user(db_session, email="isolation-worker-b@example.com")

    farm_a = create_owned_farm(db_session, owner=owner_a, name="Farm A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Farm B")

    add_staff(db_session, farm_a, worker_a, FarmRole.WORKER)
    add_staff(db_session, farm_b, worker_b, FarmRole.WORKER)

    response = client.get(
        f"/api/v1/farms/{farm_a.id}/staff",
        headers=authorization_header(owner_a),
    )

    assert response.status_code == 200

    user_ids = {member["user_id"] for member in response.json()}

    assert str(worker_a.id) in user_ids
    assert str(worker_b.id) not in user_ids
    assert str(owner_b.id) not in user_ids


def test_staff_listing_requires_authentication(client, db_session):
    owner = create_user(db_session, email="auth-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)

    response = client.get(f"/api/v1/farms/{farm.id}/staff")

    assert response.status_code == 401


def test_owner_can_view_staff_details(client, db_session):
    owner = create_user(db_session, email="details-owner@example.com")
    worker = create_user(db_session, email="details-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_staff(db_session, farm, worker, FarmRole.WORKER)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff/{member.id}",
        headers=authorization_header(owner),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["membership_id"] == str(member.id)
    assert data["user_id"] == str(worker.id)
    assert data["email"] == worker.email
    assert data["role"] == "WORKER"
    assert "password_hash" not in data


def test_manager_can_view_staff_details(client, db_session):
    owner = create_user(db_session, email="details-manager-owner@example.com")
    manager = create_user(db_session, email="details-manager@example.com")
    worker = create_user(db_session, email="details-manager-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    add_staff(db_session, farm, manager, FarmRole.FARM_MANAGER)
    worker_member = add_staff(db_session, farm, worker, FarmRole.WORKER)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff/{worker_member.id}",
        headers=authorization_header(manager),
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == str(worker.id)


@pytest.mark.parametrize(
    "role",
    [FarmRole.WORKER, FarmRole.VETERINARIAN],
)
def test_restricted_roles_cannot_view_staff_details(
    client, db_session, role
):
    owner = create_user(db_session, email="restricted-details-owner@example.com")
    user = create_user(
        db_session,
        email=f"restricted-details-{role.value.lower()}@example.com",
    )
    farm = create_owned_farm(db_session, owner=owner)
    member = add_staff(db_session, farm, user, role)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff/{member.id}",
        headers=authorization_header(user),
    )

    assert response.status_code == 403


def test_staff_details_are_isolated_between_farms(client, db_session):
    owner_a = create_user(db_session, email="details-owner-a@example.com")
    owner_b = create_user(db_session, email="details-owner-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="Farm A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Farm B")

    response = client.get(
        f"/api/v1/farms/{farm_a.id}/staff/"
        f"{db_session.query(FarmMember).filter_by(farm_id=farm_b.id).first().id}",
        headers=authorization_header(owner_a),
    )

    assert response.status_code == 404


def test_non_member_cannot_view_staff_details(client, db_session):
    owner = create_user(db_session, email="details-nonmember-owner@example.com")
    outsider = create_user(db_session, email="details-outsider@example.com")
    farm = create_owned_farm(db_session, owner=owner)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff/{farm.id}",
        headers=authorization_header(outsider),
    )

    assert response.status_code == 404


def test_staff_details_require_authentication(client, db_session):
    owner = create_user(db_session, email="details-auth-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)

    response = client.get(
        f"/api/v1/farms/{farm.id}/staff/{farm.id}"
    )

    assert response.status_code == 401


def test_owner_can_change_non_owner_operational_role(client, db_session):
    owner = create_user(db_session, email="role-change-owner@example.com")
    worker = create_user(db_session, email="role-change-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_staff(db_session, farm, worker, FarmRole.WORKER)

    response = client.patch(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/role",
        headers=authorization_header(owner),
        json={"role": "VETERINARIAN"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "VETERINARIAN"
    db_session.refresh(member)
    assert member.role == FarmRole.VETERINARIAN


def test_manager_cannot_change_staff_role(client, db_session):
    owner = create_user(db_session, email="manager-change-owner@example.com")
    manager = create_user(db_session, email="manager-change@example.com")
    worker = create_user(db_session, email="manager-change-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    add_staff(db_session, farm, manager, FarmRole.FARM_MANAGER)
    member = add_staff(db_session, farm, worker, FarmRole.WORKER)
    response = client.patch(
        f"/api/v1/farms/{farm.id}/staff/{member.id}/role",
        headers=authorization_header(manager),
        json={"role": "VETERINARIAN"},
    )
    assert response.status_code == 403


def test_owner_role_and_status_are_immutable(client, db_session):
    owner = create_user(db_session, email="immutable-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    owner_member = db_session.query(FarmMember).filter_by(
        farm_id=farm.id, user_id=owner.id
    ).one()
    role_response = client.patch(
        f"/api/v1/farms/{farm.id}/staff/{owner_member.id}/role",
        headers=authorization_header(owner),
        json={"role": "WORKER"},
    )
    status_response = client.patch(
        f"/api/v1/farms/{farm.id}/staff/{owner_member.id}/status",
        headers=authorization_header(owner),
        json={"status": "INACTIVE"},
    )
    assert role_response.status_code == 409
    assert status_response.status_code == 409


def test_owner_can_deactivate_and_reactivate_non_owner(client, db_session):
    owner = create_user(db_session, email="status-owner@example.com")
    worker = create_user(db_session, email="status-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    member = add_staff(db_session, farm, worker, FarmRole.WORKER)
    for expected in ("INACTIVE", "ACTIVE"):
        response = client.patch(
            f"/api/v1/farms/{farm.id}/staff/{member.id}/status",
            headers=authorization_header(owner),
            json={"status": expected},
        )
        assert response.status_code == 200
        assert response.json()["status"] == expected


def test_staff_filters_and_pagination_are_stable(client, db_session):
    owner = create_user(db_session, email="filter-owner@example.com")
    worker = create_user(db_session, email="filter-worker@example.com")
    vet = create_user(db_session, email="filter-vet@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    add_staff(db_session, farm, worker, FarmRole.WORKER)
    add_staff(db_session, farm, vet, FarmRole.VETERINARIAN)
    filtered = client.get(
        f"/api/v1/farms/{farm.id}/staff?role=WORKER&status=ACTIVE",
        headers=authorization_header(owner),
    )
    assert filtered.status_code == 200
    assert [item["user_id"] for item in filtered.json()] == [str(worker.id)]
    page = client.get(
        f"/api/v1/farms/{farm.id}/staff?limit=1&offset=1",
        headers=authorization_header(owner),
    )
    assert page.status_code == 200
    assert len(page.json()) == 1


def test_staff_modification_is_farm_scoped(client, db_session):
    owner_a = create_user(db_session, email="modify-a@example.com")
    owner_b = create_user(db_session, email="modify-b@example.com")
    worker_b = create_user(db_session, email="modify-worker-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="B")
    member_b = add_staff(db_session, farm_b, worker_b, FarmRole.WORKER)
    response = client.patch(
        f"/api/v1/farms/{farm_a.id}/staff/{member_b.id}/role",
        headers=authorization_header(owner_a),
        json={"role": "VETERINARIAN"},
    )
    assert response.status_code == 404
