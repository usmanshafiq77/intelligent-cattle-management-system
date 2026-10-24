import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies.farms import require_farm_owner
from app.api.v1.farms import create_farm
from app.models.farm import Farm
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.schemas.farm import FarmCreate
from tests.helpers import (
    authorization_header,
    create_owned_farm,
    create_user,
)


pytestmark = pytest.mark.integration


def test_farm_creation_also_creates_active_owner_membership(
    client,
    db_session,
):
    owner = create_user(db_session, email="farm-owner@example.com")
    response = client.post(
        "/api/v1/farms",
        json={"name": "North Farm"},
        headers=authorization_header(owner),
    )
    assert response.status_code == 201

    farm_id = response.json()["id"]
    membership = db_session.scalar(
        select(FarmMember).where(FarmMember.farm_id == farm_id)
    )
    assert membership.user_id == owner.id
    assert membership.role == FarmRole.FARM_OWNER
    assert membership.status == MemberStatus.ACTIVE


def test_owner_can_create_and_list_multiple_farms(client, db_session):
    owner = create_user(db_session, email="multi-farm@example.com")
    headers = authorization_header(owner)

    assert client.post(
        "/api/v1/farms", json={"name": "Farm One"}, headers=headers
    ).status_code == 201
    assert client.post(
        "/api/v1/farms", json={"name": "Farm Two"}, headers=headers
    ).status_code == 201

    farms = client.get("/api/v1/farms", headers=headers)
    assert farms.status_code == 200
    assert {farm["name"] for farm in farms.json()} == {
        "Farm One",
        "Farm Two",
    }


def test_cross_farm_access_is_isolated(client, db_session):
    first_owner = create_user(db_session, email="first-owner@example.com")
    second_owner = create_user(db_session, email="second-owner@example.com")
    first_farm = create_owned_farm(db_session, owner=first_owner)

    response = client.get(
        f"/api/v1/farms/{first_farm.id}",
        headers=authorization_header(second_owner),
    )
    assert response.status_code == 404


def test_inactive_membership_cannot_access_farm(client, db_session):
    owner = create_user(db_session, email="active-owner@example.com")
    worker = create_user(db_session, email="inactive-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    db_session.add(
        FarmMember(
            farm_id=farm.id,
            user_id=worker.id,
            role=FarmRole.WORKER,
            status=MemberStatus.INACTIVE,
        )
    )
    db_session.commit()

    response = client.get(
        f"/api/v1/farms/{farm.id}",
        headers=authorization_header(worker),
    )
    assert response.status_code == 404


def test_owner_can_update_farm_profile_but_worker_cannot(client, db_session):
    owner = create_user(db_session, email="farm-update-owner@example.com")
    worker = create_user(db_session, email="farm-update-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    db_session.add(
        FarmMember(
            farm_id=farm.id,
            user_id=worker.id,
            role=FarmRole.WORKER,
            status=MemberStatus.ACTIVE,
        )
    )
    db_session.commit()

    denied = client.patch(
        f"/api/v1/farms/{farm.id}",
        headers=authorization_header(worker),
        json={"name": "Unauthorized rename"},
    )
    assert denied.status_code == 403

    updated = client.patch(
        f"/api/v1/farms/{farm.id}",
        headers=authorization_header(owner),
        json={
            "name": "Updated Farm",
            "location": "Lahore",
            "description": "Updated profile",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated Farm"
    assert updated.json()["location"] == "Lahore"


def test_farm_update_rejects_empty_or_null_name(client, db_session):
    owner = create_user(db_session, email="farm-update-validation@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    headers = authorization_header(owner)

    assert client.patch(
        f"/api/v1/farms/{farm.id}", headers=headers, json={}
    ).status_code == 422
    assert client.patch(
        f"/api/v1/farms/{farm.id}", headers=headers, json={"name": None}
    ).status_code == 422


def test_farm_creation_rolls_back_both_records_on_commit_failure(
    db_session,
    monkeypatch,
):
    owner = create_user(db_session, email="rollback-owner@example.com")

    def fail_commit():
        db_session.flush()
        raise SQLAlchemyError("forced commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(SQLAlchemyError):
        create_farm(
            data=FarmCreate(name="Rollback Farm"),
            db=db_session,
            current_user=owner,
        )

    assert db_session.scalar(
        select(func.count(Farm.id)).where(Farm.name == "Rollback Farm")
    ) == 0
    assert db_session.scalar(select(func.count(FarmMember.id))) == 0


def test_authoritative_owner_mismatch_is_rejected(db_session):
    authoritative_owner = create_user(
        db_session,
        email="authoritative@example.com",
    )
    unrelated_user = create_user(
        db_session,
        email="unrelated-owner@example.com",
    )
    farm = Farm(name="Inconsistent Farm", owner_id=authoritative_owner.id)
    db_session.add(farm)
    db_session.flush()
    db_session.add(
        FarmMember(
            farm_id=farm.id,
            user_id=unrelated_user.id,
            role=FarmRole.FARM_OWNER,
            status=MemberStatus.ACTIVE,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as error:
        require_farm_owner(
            farm_id=farm.id,
            db=db_session,
            current_user=authoritative_owner,
        )
    assert error.value.status_code == 403
