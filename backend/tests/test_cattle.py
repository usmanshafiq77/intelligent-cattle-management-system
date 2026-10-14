import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.models.cattle import (
    AnimalCategory,
    AnimalSex,
    Breed,
    Cattle,
    CattleLifecycleEvent,
    CattleStatus,
    CattleWeightRecord,
    Species,
)
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.farm import Farm
from app.models.user import User
from tests.helpers import authorization_header, create_owned_farm, create_user
from tests.test_rbac import create_role


pytestmark = pytest.mark.integration

HOLSTEIN_ID = "15a83daf-5c4a-5cb9-8bed-5a4e7ea1e035"
BUFFALO_BREED_ID = "7e9a2385-f882-51c4-9940-c9c9fb2ea34e"


def add_member(db, farm, user, role, status=MemberStatus.ACTIVE):
    membership = FarmMember(
        farm_id=farm.id,
        user_id=user.id,
        role=role,
        status=status,
    )
    db.add(membership)
    db.commit()
    return membership


def cattle_payload(tag="TAG-001", **overrides):
    payload = {
        "tag_number": tag,
        "name": "Daisy",
        "species": "CATTLE",
        "sex": "FEMALE",
        "category": "COW",
        "breed_id": HOLSTEIN_ID,
        "date_of_birth": "2022-01-15",
        "acquisition_date": "2023-01-15",
        "acquisition_method": "PURCHASED",
        "color": "Brown and white",
    }
    payload.update(overrides)
    return payload


def register(client, farm, user, tag="TAG-001", **overrides):
    return client.post(
        f"/api/v1/farms/{farm.id}/cattle",
        headers=authorization_header(user),
        json=cattle_payload(tag, **overrides),
    )


def test_owner_registration_atomically_creates_weight_and_event(client, db_session):
    owner = create_user(db_session, email="cattle-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    measured_at = datetime.now(timezone.utc) - timedelta(hours=1)
    response = register(
        client,
        farm,
        owner,
        initial_weight_kg="455.25",
        initial_weight_measured_at=measured_at.isoformat(),
        initial_weight_method="digital scale",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["farm_id"] == str(farm.id)
    assert data["latest_weight"]["weight_kg"] == "455.25"
    assert data["breed"]["name"] == "Holstein"
    cattle_id = data["id"]
    assert db_session.scalar(
        select(func.count(CattleLifecycleEvent.id)).where(
            CattleLifecycleEvent.cattle_id == cattle_id
        )
    ) == 1
    assert db_session.scalar(
        select(func.count(CattleWeightRecord.id)).where(
            CattleWeightRecord.cattle_id == cattle_id
        )
    ) == 1


def test_manager_can_register_but_worker_cannot(client, db_session):
    owner = create_user(db_session, email="cattle-policy-owner@example.com")
    manager = create_user(db_session, email="cattle-manager@example.com")
    worker = create_user(db_session, email="cattle-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    add_member(db_session, farm, manager, FarmRole.FARM_MANAGER)
    add_member(db_session, farm, worker, FarmRole.WORKER)
    assert register(client, farm, manager, "MGR-1").status_code == 201
    assert register(client, farm, worker, "WORKER-1").status_code == 403


def test_custom_cattle_creator_role_extends_worker_permissions(client, db_session):
    owner = create_user(db_session, email="custom-cattle-owner@example.com")
    worker = create_user(db_session, email="custom-cattle-worker@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    membership = add_member(db_session, farm, worker, FarmRole.WORKER)
    role_id = create_role(
        client,
        owner,
        farm,
        name="Registrar",
        permissions=["cattle.create"],
    ).json()["id"]
    assigned = client.post(
        f"/api/v1/farms/{farm.id}/staff/{membership.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [role_id]},
    )
    assert assigned.status_code == 200
    assert register(client, farm, worker, "CUSTOM-1").status_code == 201


def test_inactive_member_cannot_register_or_view(client, db_session):
    owner = create_user(db_session, email="cattle-inactive-owner@example.com")
    manager = create_user(db_session, email="cattle-inactive-manager@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    add_member(
        db_session,
        farm,
        manager,
        FarmRole.FARM_MANAGER,
        MemberStatus.INACTIVE,
    )
    assert register(client, farm, manager).status_code == 404
    assert client.get(
        f"/api/v1/farms/{farm.id}/cattle",
        headers=authorization_header(manager),
    ).status_code == 404


def test_tag_is_normalized_per_farm_but_reusable_across_farms(client, db_session):
    owner_a = create_user(db_session, email="tag-owner-a@example.com")
    owner_b = create_user(db_session, email="tag-owner-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="Tag A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Tag B")
    assert register(client, farm_a, owner_a, " Tag   9 ").status_code == 201
    duplicate = register(client, farm_a, owner_a, "tag 9")
    assert duplicate.status_code == 409
    assert register(client, farm_b, owner_b, "TAG 9").status_code == 201


def test_cross_farm_cattle_profile_is_not_disclosed(client, db_session):
    owner_a = create_user(db_session, email="profile-a@example.com")
    owner_b = create_user(db_session, email="profile-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="Profile A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Profile B")
    cattle_id = register(client, farm_b, owner_b).json()["id"]
    response = client.get(
        f"/api/v1/farms/{farm_a.id}/cattle/{cattle_id}",
        headers=authorization_header(owner_a),
    )
    assert response.status_code == 404


def test_cattle_routes_require_authentication(client, db_session):
    owner = create_user(db_session, email="cattle-auth-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    assert client.get(f"/api/v1/farms/{farm.id}/cattle").status_code == 401
    assert client.post(
        f"/api/v1/farms/{farm.id}/cattle", json=cattle_payload()
    ).status_code == 401


def test_listing_search_filters_and_pagination(client, db_session):
    owner = create_user(db_session, email="directory-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    register(client, farm, owner, "DIR-1", name="Alpha")
    register(
        client,
        farm,
        owner,
        "DIR-2",
        name="Buffy",
        species="BUFFALO",
        breed_id=BUFFALO_BREED_ID,
    )
    headers = authorization_header(owner)
    searched = client.get(
        f"/api/v1/farms/{farm.id}/cattle?search=alpha",
        headers=headers,
    )
    assert searched.status_code == 200
    assert [item["tag_number"] for item in searched.json()] == ["DIR-1"]
    buffalo = client.get(
        f"/api/v1/farms/{farm.id}/cattle?species=BUFFALO",
        headers=headers,
    )
    assert [item["tag_number"] for item in buffalo.json()] == ["DIR-2"]
    page = client.get(
        f"/api/v1/farms/{farm.id}/cattle?limit=1&offset=1",
        headers=headers,
    )
    assert page.status_code == 200
    assert len(page.json()) == 1


def test_profile_update_preserves_identity_history_and_explicit_null(client, db_session):
    owner = create_user(db_session, email="update-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    created = register(
        client, farm, owner, initial_weight_kg="400", notes="Original"
    ).json()
    response = client.patch(
        f"/api/v1/farms/{farm.id}/cattle/{created['id']}",
        headers=authorization_header(owner),
        json={"name": None, "breed_id": None, "notes": "Updated"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["name"] is None
    assert data["breed"] is None
    assert data["latest_weight"]["weight_kg"] == "400.00"
    assert data["notes"] == "Updated"


@pytest.mark.parametrize(
    "payload",
    [
        {"tag_number": None},
        {"category": None},
        {"birth_date_estimated": True, "date_of_birth": None},
        {"date_of_birth": "2999-01-01"},
        {"status": "DECEASED"},
    ],
)
def test_profile_update_rejects_inconsistent_values(
    client, db_session, payload
):
    owner = create_user(
        db_session, email=f"invalid-update-{uuid.uuid4().hex}@example.com"
    )
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    response = client.patch(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}",
        headers=authorization_header(owner),
        json=payload,
    )
    assert response.status_code == 422


def test_invalid_update_does_not_partially_change_tag(client, db_session):
    owner = create_user(db_session, email="atomic-update-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    created = register(client, farm, owner, "ATOMIC-OLD").json()
    response = client.patch(
        f"/api/v1/farms/{farm.id}/cattle/{created['id']}",
        headers=authorization_header(owner),
        json={"tag_number": "ATOMIC-NEW", "breed_id": BUFFALO_BREED_ID},
    )
    assert response.status_code == 422
    unchanged = client.get(
        f"/api/v1/farms/{farm.id}/cattle/{created['id']}",
        headers=authorization_header(owner),
    )
    assert unchanged.json()["tag_number"] == "ATOMIC-OLD"


def test_acquisition_cost_requires_iso_currency(client, db_session):
    owner = create_user(db_session, email="cost-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    invalid = register(
        client, farm, owner, "COST-1", initial_acquisition_cost="100000"
    )
    assert invalid.status_code == 422
    valid = register(
        client,
        farm,
        owner,
        "COST-2",
        initial_acquisition_cost="100000",
        initial_acquisition_currency="pkr",
    )
    assert valid.status_code == 201
    assert valid.json()["initial_acquisition_currency"] == "PKR"


def test_breed_species_and_category_sex_are_validated(client, db_session):
    owner = create_user(db_session, email="classification-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    wrong_breed = register(
        client, farm, owner, "CLASS-1", breed_id=BUFFALO_BREED_ID
    )
    wrong_category = register(
        client,
        farm,
        owner,
        "CLASS-2",
        sex="MALE",
        category="COW",
    )
    assert wrong_breed.status_code == 422
    assert wrong_category.status_code == 422


def test_breed_catalog_listing_details_and_admin_uniqueness(client, db_session):
    user = create_user(db_session, email="breed-user@example.com")
    admin = create_user(db_session, email="breed-admin@example.com")
    admin.is_system_admin = True
    db_session.commit()
    listing = client.get(
        "/api/v1/breeds?species=CATTLE",
        headers=authorization_header(user),
    )
    assert listing.status_code == 200
    assert {breed["species"] for breed in listing.json()} == {"CATTLE"}
    detail = client.get(
        f"/api/v1/breeds/{HOLSTEIN_ID}",
        headers=authorization_header(user),
    )
    assert detail.status_code == 200
    assert detail.json()["name"] == "Holstein"
    denied = client.post(
        "/api/v1/breeds",
        headers=authorization_header(user),
        json={"name": "New Breed", "species": "CATTLE"},
    )
    assert denied.status_code == 403
    created = client.post(
        "/api/v1/breeds",
        headers=authorization_header(admin),
        json={"name": "New Breed", "species": "CATTLE"},
    )
    assert created.status_code == 201
    duplicate = client.post(
        "/api/v1/breeds",
        headers=authorization_header(admin),
        json={"name": " new   breed ", "species": "CATTLE"},
    )
    assert duplicate.status_code == 409


def test_failed_initial_profile_validation_leaves_no_partial_rows(client, db_session):
    owner = create_user(db_session, email="rollback-cattle-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    response = register(
        client,
        farm,
        owner,
        "ROLLBACK-1",
        breed_id=str(uuid.uuid4()),
        initial_weight_kg="450",
    )
    assert response.status_code == 422
    assert db_session.scalar(
        select(func.count(Cattle.id)).where(Cattle.farm_id == farm.id)
    ) == 0
    assert db_session.scalar(select(func.count(CattleWeightRecord.id))) == 0


def test_weight_history_is_ordered_and_updates_latest_weight(client, db_session):
    owner = create_user(db_session, email="weight-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    headers = authorization_header(owner)
    older = datetime.now(timezone.utc) - timedelta(days=2)
    newer = datetime.now(timezone.utc) - timedelta(days=1)
    for weight, measured in (("410", older), ("425.5", newer)):
        response = client.post(
            f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/weights",
            headers=headers,
            json={"weight_kg": weight, "measured_at": measured.isoformat()},
        )
        assert response.status_code == 201
    history = client.get(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/weights",
        headers=headers,
    ).json()
    assert [item["weight_kg"] for item in history] == ["425.50", "410.00"]
    profile = client.get(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}", headers=headers
    ).json()
    assert profile["latest_weight"]["weight_kg"] == "425.50"


@pytest.mark.parametrize("weight", ["0", "-1", "3000.01"])
def test_weight_validation(client, db_session, weight):
    owner = create_user(
        db_session, email=f"weight-invalid-{uuid.uuid4().hex}@example.com"
    )
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    response = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/weights",
        headers=authorization_header(owner),
        json={"weight_kg": weight, "measured_at": datetime.now(timezone.utc).isoformat()},
    )
    assert response.status_code == 422


def test_future_weight_measurement_is_rejected(client, db_session):
    owner = create_user(db_session, email="future-weight-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    response = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/weights",
        headers=authorization_header(owner),
        json={
            "weight_kg": "400",
            "measured_at": (
                datetime.now(timezone.utc) + timedelta(days=1)
            ).isoformat(),
        },
    )
    assert response.status_code == 422


def test_lifecycle_transition_and_append_only_history(client, db_session):
    owner = create_user(db_session, email="lifecycle-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    effective = datetime.now(timezone.utc)
    transitioned = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/lifecycle",
        headers=authorization_header(owner),
        json={
            "new_status": "MISSING",
            "effective_at": effective.isoformat(),
            "reason": "Not found in pasture",
        },
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["previous_status"] == "ACTIVE"
    history = client.get(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/lifecycle",
        headers=authorization_header(owner),
    ).json()
    assert [event["new_status"] for event in history] == ["MISSING", "ACTIVE"]
    reactivated = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/lifecycle",
        headers=authorization_header(owner),
        json={
            "new_status": "ACTIVE",
            "effective_at": datetime.now(timezone.utc).isoformat(),
            "reason": "Recovered",
        },
    )
    assert reactivated.status_code == 200


def test_terminal_lifecycle_status_cannot_be_arbitrarily_reactivated(client, db_session):
    owner = create_user(db_session, email="terminal-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    headers = authorization_header(owner)
    sold = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/lifecycle",
        headers=headers,
        json={
            "new_status": "SOLD",
            "effective_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert sold.status_code == 200
    invalid = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/lifecycle",
        headers=headers,
        json={
            "new_status": "ACTIVE",
            "effective_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert invalid.status_code == 422


def test_parent_links_enforce_farm_species_and_sex(client, db_session):
    owner_a = create_user(db_session, email="parent-owner-a@example.com")
    owner_b = create_user(db_session, email="parent-owner-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="Parents A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Parents B")
    mother = register(client, farm_a, owner_a, "MOTHER").json()
    father = register(
        client,
        farm_a,
        owner_a,
        "FATHER",
        name="Bull",
        sex="MALE",
        category="BULL",
    ).json()
    foreign = register(client, farm_b, owner_b, "FOREIGN").json()
    child = register(
        client,
        farm_a,
        owner_a,
        "CHILD",
        category="CALF",
        mother_id=mother["id"],
        father_id=father["id"],
    )
    assert child.status_code == 201
    rejected = register(
        client,
        farm_a,
        owner_a,
        "CHILD-2",
        category="CALF",
        mother_id=foreign["id"],
    )
    assert rejected.status_code == 422


def test_database_rejects_cross_farm_weight_link(db_session):
    owner_a = create_user(db_session, email="fk-weight-a@example.com")
    owner_b = create_user(db_session, email="fk-weight-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="Weight A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Weight B")
    animal = Cattle(
        farm_id=farm_a.id,
        tag_number="FK-1",
        normalized_tag="fk-1",
        species=Species.CATTLE,
        sex=AnimalSex.FEMALE,
        category=AnimalCategory.COW,
        created_by_id=owner_a.id,
    )
    db_session.add(animal)
    db_session.commit()
    db_session.add(
        CattleWeightRecord(
            cattle_id=animal.id,
            farm_id=farm_b.id,
            weight_kg=Decimal("400"),
            measured_at=datetime.now(timezone.utc),
            recorded_by_id=owner_b.id,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_concurrent_lifecycle_updates_serialize(pg_engine):
    unique = uuid.uuid4().hex
    setup = Session(pg_engine, expire_on_commit=False)
    owner = create_user(setup, email=f"concurrent-cattle-{unique}@example.com")
    farm = create_owned_farm(setup, owner=owner, name=f"Concurrent {unique}")
    animal = Cattle(
        farm_id=farm.id,
        tag_number=f"CONCURRENT-{unique}",
        normalized_tag=f"concurrent-{unique}",
        species=Species.CATTLE,
        sex=AnimalSex.FEMALE,
        category=AnimalCategory.COW,
        created_by_id=owner.id,
    )
    setup.add(animal)
    setup.commit()
    owner_id, farm_id, cattle_id = owner.id, farm.id, animal.id
    headers = authorization_header(owner)
    setup.close()
    barrier = threading.Barrier(2)

    def override_db():
        session = Session(pg_engine, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    test_client = TestClient(app)

    def transition(new_status):
        barrier.wait()
        return test_client.post(
            f"/api/v1/farms/{farm_id}/cattle/{cattle_id}/lifecycle",
            headers=headers,
            json={
                "new_status": new_status,
                "effective_at": datetime.now(timezone.utc).isoformat(),
            },
        ).status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(transition, ("MISSING", "SOLD")))
    finally:
        test_client.close()
        app.dependency_overrides.clear()
    assert sorted(results) == [200, 422]
    cleanup = Session(pg_engine)
    cleanup.execute(
        delete(CattleLifecycleEvent).where(
            CattleLifecycleEvent.cattle_id == cattle_id
        )
    )
    cleanup.execute(delete(Cattle).where(Cattle.id == cattle_id))
    cleanup.execute(delete(Farm).where(Farm.id == farm_id))
    cleanup.execute(delete(User).where(User.id == owner_id))
    cleanup.commit()
    cleanup.close()


def test_openapi_contains_complete_cattle_contract():
    paths = app.openapi()["paths"]
    required = {
        "/api/v1/breeds": {"get", "post"},
        "/api/v1/breeds/{breed_id}": {"get"},
        "/api/v1/farms/{farm_id}/cattle": {"get", "post"},
        "/api/v1/farms/{farm_id}/cattle/{cattle_id}": {"get", "patch"},
        "/api/v1/farms/{farm_id}/cattle/{cattle_id}/lifecycle": {
            "get",
            "post",
        },
        "/api/v1/farms/{farm_id}/cattle/{cattle_id}/weights": {
            "get",
            "post",
        },
        "/api/v1/farms/{farm_id}/cattle/{cattle_id}/media": {
            "get",
            "post",
        },
        "/api/v1/farms/{farm_id}/cattle/{cattle_id}/media/{media_id}": {
            "get",
            "delete",
        },
    }
    for path, methods in required.items():
        assert methods <= set(paths[path])
