import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import func, select

from app.models.cattle import AnimalCategory, AnimalSex, Cattle, Species
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.feed import FeedStockMovement
from tests.helpers import authorization_header, create_owned_farm, create_user


pytestmark = pytest.mark.integration


def setup_farm(db, *, suffix=None):
    suffix = suffix or uuid.uuid4().hex[:8]
    owner = create_user(db, email=f"feed-owner-{suffix}@example.com")
    farm = create_owned_farm(db, owner=owner, name=f"Feed Farm {suffix}")
    cattle = Cattle(
        farm_id=farm.id,
        tag_number=f"F-{suffix}",
        normalized_tag=f"f-{suffix}",
        species=Species.CATTLE,
        sex=AnimalSex.FEMALE,
        category=AnimalCategory.COW,
        created_by_id=owner.id,
    )
    db.add(cattle)
    db.commit()
    return owner, farm, cattle


def add_member(db, farm, role):
    user = create_user(db, email=f"feed-{role.value.lower()}-{uuid.uuid4().hex[:8]}@example.com")
    db.add(FarmMember(farm_id=farm.id, user_id=user.id, role=role, status=MemberStatus.ACTIVE))
    db.commit()
    return user


def create_item(client, farm, actor, **overrides):
    payload = {
        "name": f"Hay {uuid.uuid4().hex[:6]}",
        "category": "FORAGE",
        "unit": "KG",
        "reorder_level": "25.000",
        "description": "Dry forage",
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/farms/{farm.id}/feed/items",
        headers=authorization_header(actor),
        json=payload,
    )


def purchase(client, farm, actor, item_id, quantity="100", request_id=None, **overrides):
    payload = {
        "client_request_id": str(request_id or uuid.uuid4()),
        "feed_item_id": item_id,
        "quantity": quantity,
        "unit": "KG",
        "unit_cost": "2.5000",
        "currency": "PKR",
        "supplier": "Farm Supplier",
        "reference": "INV-1",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/farms/{farm.id}/feed/stock/purchases",
        headers=authorization_header(actor),
        json=payload,
    )


def test_inventory_crud_purchase_adjustment_and_low_stock(client, db_session):
    owner, farm, _ = setup_farm(db_session)
    created = create_item(client, farm, owner, name="Alfalfa Hay")
    assert created.status_code == 201
    item = created.json()
    assert item["current_quantity"] == "0.000"
    assert item["low_stock"] is True

    bought = purchase(client, farm, owner, item["id"])
    assert bought.status_code == 201
    assert bought.json()["resulting_quantity"] == "100.000"
    assert bought.json()["total_cost"] == "250.0000000"

    adjusted = client.post(
        f"/api/v1/farms/{farm.id}/feed/stock/adjustments",
        headers=authorization_header(owner),
        json={
            "client_request_id": str(uuid.uuid4()),
            "feed_item_id": item["id"],
            "direction": "OUT",
            "quantity": "80",
            "unit": "KG",
            "reason": "Verified storage loss",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert adjusted.status_code == 201
    alerts = client.get(
        f"/api/v1/farms/{farm.id}/feed/alerts/low-stock",
        headers=authorization_header(owner),
    )
    assert alerts.status_code == 200
    assert alerts.json()[0]["current_quantity"] == "20.000"

    updated = client.patch(
        f"/api/v1/farms/{farm.id}/feed/items/{item['id']}",
        headers=authorization_header(owner),
        json={"reorder_level": "30", "description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated"


def test_duplicate_transactions_units_and_negative_inventory_are_rejected(client, db_session):
    owner, farm, _ = setup_farm(db_session)
    item = create_item(client, farm, owner).json()
    request_id = uuid.uuid4()
    assert purchase(client, farm, owner, item["id"], quantity="10", request_id=request_id).status_code == 201
    assert purchase(client, farm, owner, item["id"], quantity="10", request_id=request_id).status_code == 409
    assert purchase(client, farm, owner, item["id"], unit="L").status_code == 422
    insufficient = client.post(
        f"/api/v1/farms/{farm.id}/feed/stock/adjustments",
        headers=authorization_header(owner),
        json={
            "client_request_id": str(uuid.uuid4()),
            "feed_item_id": item["id"],
            "direction": "OUT",
            "quantity": "11",
            "unit": "KG",
            "reason": "Count correction",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert insufficient.status_code == 409


def test_schedule_and_consumption_deduct_stock_and_are_idempotent(client, db_session):
    owner, farm, cattle = setup_farm(db_session)
    item = create_item(client, farm, owner).json()
    assert purchase(client, farm, owner, item["id"], quantity="50").status_code == 201
    schedule = client.post(
        f"/api/v1/farms/{farm.id}/feed/schedules",
        headers=authorization_header(owner),
        json={
            "name": "Morning cow ration",
            "feed_item_id": item["id"],
            "target_type": "CATTLE",
            "cattle_id": str(cattle.id),
            "quantity_per_head": "5",
            "unit": "KG",
            "frequency": "DAILY",
            "days_of_week": [],
            "feeding_time": "07:30:00",
            "start_date": date.today().isoformat(),
        },
    )
    assert schedule.status_code == 201
    request_id = uuid.uuid4()
    payload = {
        "client_request_id": str(request_id),
        "feed_item_id": item["id"],
        "schedule_id": schedule.json()["id"],
        "target_type": "CATTLE",
        "cattle_id": str(cattle.id),
        "feeding_date": date.today().isoformat(),
        "quantity": "5",
        "unit": "KG",
    }
    consumed = client.post(
        f"/api/v1/farms/{farm.id}/feed/consumption",
        headers=authorization_header(owner), json=payload,
    )
    assert consumed.status_code == 201
    duplicate = client.post(
        f"/api/v1/farms/{farm.id}/feed/consumption",
        headers=authorization_header(owner), json=payload,
    )
    assert duplicate.status_code == 409
    inventory = client.get(
        f"/api/v1/farms/{farm.id}/feed/items",
        headers=authorization_header(owner),
    ).json()
    assert inventory[0]["current_quantity"] == "45.000"
    assert db_session.scalar(select(func.count(FeedStockMovement.id))) == 2


def test_nutrition_plan_has_explicit_non_approval_advisory(client, db_session):
    owner, farm, cattle = setup_farm(db_session)
    item = create_item(client, farm, owner, name="Mineral Mix", category="MINERAL", unit="G").json()
    created = client.post(
        f"/api/v1/farms/{farm.id}/feed/nutrition-plans",
        headers=authorization_header(owner),
        json={
            "name": "Lactating cow plan",
            "target_type": "CATTLE",
            "cattle_id": str(cattle.id),
            "objective": "Support routine lactation feeding",
            "start_date": date.today().isoformat(),
            "lines": [{
                "feed_item_id": item["id"],
                "daily_quantity_per_head": "120",
                "unit": "G",
            }],
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "DRAFT"
    assert created.json()["professional_review_required"] is True
    assert "not automatically veterinarian-approved" in created.json()["advisory"]
    reviewed = client.patch(
        f"/api/v1/farms/{farm.id}/feed/nutrition-plans/{created.json()['id']}",
        headers=authorization_header(owner), json={"status": "REVIEWED"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewed_by_id"] == str(owner.id)


def test_feed_reports_separate_consumption_from_financial_data(client, db_session):
    owner, farm, cattle = setup_farm(db_session)
    item = create_item(client, farm, owner).json()
    purchase(client, farm, owner, item["id"], quantity="20")
    client.post(
        f"/api/v1/farms/{farm.id}/feed/consumption",
        headers=authorization_header(owner),
        json={
            "client_request_id": str(uuid.uuid4()),
            "feed_item_id": item["id"],
            "target_type": "CATTLE",
            "cattle_id": str(cattle.id),
            "feeding_date": date.today().isoformat(),
            "quantity": "2",
            "unit": "KG",
        },
    )
    params = {"date_from": date.today().isoformat(), "date_to": date.today().isoformat()}
    summary = client.get(
        f"/api/v1/farms/{farm.id}/feed/reports/summary",
        headers=authorization_header(owner), params=params,
    )
    costs = client.get(
        f"/api/v1/farms/{farm.id}/feed/reports/costs",
        headers=authorization_header(owner), params=params,
    )
    assert summary.status_code == costs.status_code == 200
    assert summary.json()["consumption_quantity_by_unit"] == {"KG": "2.000"}
    assert "purchase_cost_by_currency" not in summary.json() or summary.json()["purchase_cost_by_currency"] is None
    assert costs.json()["purchase_cost_by_currency"] == {"PKR": "50.0000000"}


def test_worker_rbac_and_veterinarian_financial_separation(client, db_session):
    owner, farm, cattle = setup_farm(db_session)
    worker = add_member(db_session, farm, FarmRole.WORKER)
    vet = add_member(db_session, farm, FarmRole.VETERINARIAN)
    item = create_item(client, farm, owner).json()
    purchase(client, farm, owner, item["id"], quantity="10")

    assert client.get(
        f"/api/v1/farms/{farm.id}/feed/items", headers=authorization_header(worker)
    ).status_code == 200
    assert create_item(client, farm, worker).status_code == 403
    recorded = client.post(
        f"/api/v1/farms/{farm.id}/feed/consumption",
        headers=authorization_header(worker),
        json={
            "client_request_id": str(uuid.uuid4()), "feed_item_id": item["id"],
            "target_type": "CATTLE", "cattle_id": str(cattle.id),
            "feeding_date": date.today().isoformat(), "quantity": "1", "unit": "KG",
        },
    )
    assert recorded.status_code == 201
    assert client.get(
        f"/api/v1/farms/{farm.id}/feed/nutrition-plans", headers=authorization_header(vet)
    ).status_code == 200
    assert client.get(
        f"/api/v1/farms/{farm.id}/feed/reports/costs",
        headers=authorization_header(vet),
        params={"date_from": date.today().isoformat(), "date_to": date.today().isoformat()},
    ).status_code == 403


def test_cross_farm_feed_ids_are_not_visible_or_mutable(client, db_session):
    owner_a, farm_a, _ = setup_farm(db_session)
    owner_b, farm_b, _ = setup_farm(db_session)
    item_a = create_item(client, farm_a, owner_a).json()
    assert client.patch(
        f"/api/v1/farms/{farm_b.id}/feed/items/{item_a['id']}",
        headers=authorization_header(owner_b), json={"description": "cross farm"},
    ).status_code == 404
    assert purchase(client, farm_b, owner_b, item_a["id"]).status_code == 422


def test_system_admin_without_membership_cannot_access_private_feed(client, db_session):
    owner, farm, _ = setup_farm(db_session)
    admin = create_user(db_session, email=f"feed-admin-{uuid.uuid4().hex[:8]}@example.com")
    admin.is_system_admin = True
    db_session.commit()
    response = client.get(
        f"/api/v1/farms/{farm.id}/feed/items",
        headers=authorization_header(admin),
    )
    assert response.status_code == 404
