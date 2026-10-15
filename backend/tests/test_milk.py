import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.milk import MilkRecordCorrection, MilkingSession
from tests.helpers import authorization_header, create_owned_farm, create_user


pytestmark = pytest.mark.integration
HOLSTEIN_ID = "15a83daf-5c4a-5cb9-8bed-5a4e7ea1e035"


def setup_farm(client, db, suffix=None, **animal_overrides):
    suffix = suffix or uuid.uuid4().hex[:10]
    owner = create_user(db, email=f"milk-{suffix}@example.com")
    farm = create_owned_farm(db, owner=owner, name=f"Milk {suffix}")
    payload = {
        "tag_number": f"M-{suffix}", "species": "CATTLE", "sex": "FEMALE",
        "category": "COW", "breed_id": HOLSTEIN_ID, "date_of_birth": "2022-01-01",
    }
    payload.update(animal_overrides)
    response = client.post(
        f"/api/v1/farms/{farm.id}/cattle",
        headers=authorization_header(owner), json=payload,
    )
    assert response.status_code == 201
    return owner, farm, response.json()


def lactation(client, farm, user, cattle_id, sequence=1, start="2026-01-01"):
    return client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations",
        headers=authorization_header(user),
        json={"cattle_id": cattle_id, "sequence_number": sequence, "start_date": start},
    )


def session(client, farm, user, cattle_id, lactation_id, **overrides):
    payload = {
        "cattle_id": cattle_id, "lactation_id": lactation_id,
        "milking_date": "2026-01-02", "session_kind": "MORNING",
        "session_code": "MORNING", "volume_liters": "10.250", "unit": "L",
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/farms/{farm.id}/milk/sessions",
        headers=authorization_header(user), json=payload,
    )


def test_lactation_create_active_history_and_transitions(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    created = lactation(client, farm, owner, animal["id"])
    assert created.status_code == 201
    active = client.get(
        f"/api/v1/farms/{farm.id}/milk/lactations/active",
        params={"cattle_id": animal["id"]}, headers=authorization_header(owner),
    )
    assert active.status_code == 200
    dry = client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations/{created.json()['id']}/transition",
        headers=authorization_header(owner), json={"status": "DRY", "effective_date": "2026-02-01"},
    )
    assert dry.status_code == 200 and dry.json()["status"] == "DRY"
    completed = client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations/{created.json()['id']}/transition",
        headers=authorization_header(owner), json={"status": "COMPLETED", "effective_date": "2026-02-02"},
    )
    assert completed.status_code == 200
    history = client.get(
        f"/api/v1/farms/{farm.id}/milk/lactations",
        params={"cattle_id": animal["id"]}, headers=authorization_header(owner),
    )
    assert len(history.json()) == 1


@pytest.mark.parametrize("overrides", [
    {"sex": "MALE", "category": "BULL"},
    {"sex": "FEMALE", "category": "HEIFER"},
])
def test_lactation_rejects_noneligible_cattle(client, db_session, overrides):
    owner, farm, animal = setup_farm(client, db_session, **overrides)
    assert lactation(client, farm, owner, animal["id"]).status_code == 422


def test_lactation_rejects_missing_duplicate_and_overlap(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    assert lactation(client, farm, owner, str(uuid.uuid4())).status_code == 404
    assert lactation(client, farm, owner, animal["id"]).status_code == 201
    assert lactation(client, farm, owner, animal["id"], 1, "2026-01-05").status_code in {409, 422}
    assert lactation(client, farm, owner, animal["id"], 2, "2026-01-05").status_code == 422


def test_lactation_invalid_completion(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    record = lactation(client, farm, owner, animal["id"]).json()
    response = client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations/{record['id']}/transition",
        headers=authorization_header(owner), json={"status": "COMPLETED", "effective_date": "2025-12-31"},
    )
    assert response.status_code == 422


def test_morning_evening_and_additional_sessions(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    morning = session(client, farm, owner, animal["id"], lac["id"])
    evening = session(client, farm, owner, animal["id"], lac["id"], session_kind="EVENING", session_code="EVENING", volume_liters="8.125")
    extra = session(client, farm, owner, animal["id"], lac["id"], session_kind="ADDITIONAL", session_code="MIDDAY_1", volume_liters="2")
    assert [morning.status_code, evening.status_code, extra.status_code] == [201, 201, 201]
    assert morning.json()["unit"] == "L"


@pytest.mark.parametrize("field,value", [
    ("volume_liters", "-1"), ("unit", "KG"),
    ("milking_date", "2099-01-01"), ("session_code", "EVENING"),
])
def test_session_input_validation(client, db_session, field, value):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    assert session(client, farm, owner, animal["id"], lac["id"], **{field: value}).status_code == 422


def test_zero_volume_is_explicitly_accepted_and_duplicate_rejected(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    first = session(client, farm, owner, animal["id"], lac["id"], volume_liters="0")
    assert first.status_code == 201 and first.json()["volume_liters"] == "0.000"
    assert session(client, farm, owner, animal["id"], lac["id"]).status_code == 409


def test_quality_validation_history_and_correction(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    milk = session(client, farm, owner, animal["id"], lac["id"]).json()
    quality = client.post(
        f"/api/v1/farms/{farm.id}/milk/quality", headers=authorization_header(owner),
        json={"session_id": milk["id"], "fat_percent": "4.1", "protein_percent": "3.2", "tested_at": "2026-01-02T12:00:00Z"},
    )
    assert quality.status_code == 201
    correction = client.post(
        f"/api/v1/farms/{farm.id}/milk/corrections", headers=authorization_header(owner),
        json={"cattle_id": animal["id"], "target_type": "QUALITY", "target_id": quality.json()["id"], "reason": "Lab instrument recalibrated", "replacement_values": {"fat_percent": "4.3"}},
    )
    assert correction.status_code == 201
    retrieved = client.get(
        f"/api/v1/farms/{farm.id}/milk/quality/{quality.json()['id']}", headers=authorization_header(owner),
    )
    assert retrieved.json()["effective_values"]["fat_percent"] == "4.3"
    assert db_session.scalar(select(func.count(MilkRecordCorrection.id))) == 1


@pytest.mark.parametrize("payload", [
    {"fat_percent": "101"}, {}, {"temperature_celsius": "-274"}, {"somatic_cell_count": -1},
])
def test_quality_rejects_invalid_measurements(client, db_session, payload):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    milk = session(client, farm, owner, animal["id"], lac["id"]).json()
    payload.update({"session_id": milk["id"], "tested_at": "2026-01-02T12:00:00Z"})
    assert client.post(f"/api/v1/farms/{farm.id}/milk/quality", headers=authorization_header(owner), json=payload).status_code == 422


def test_quality_rejects_cross_farm_session(client, db_session):
    owner_a, farm_a, _ = setup_farm(client, db_session, "qa")
    owner_b, farm_b, animal_b = setup_farm(client, db_session, "qb")
    lac = lactation(client, farm_b, owner_b, animal_b["id"]).json()
    milk = session(client, farm_b, owner_b, animal_b["id"], lac["id"]).json()
    response = client.post(
        f"/api/v1/farms/{farm_a.id}/milk/quality", headers=authorization_header(owner_a),
        json={"session_id": milk["id"], "fat_percent": "4", "tested_at": "2026-01-02T12:00:00Z"},
    )
    assert response.status_code == 404


def test_bulk_is_atomic_for_valid_batch_and_duplicate_batch(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    base = {"cattle_id": animal["id"], "lactation_id": lac["id"], "milking_date": "2026-01-03", "volume_liters": "5", "unit": "L"}
    valid = client.post(
        f"/api/v1/farms/{farm.id}/milk/sessions/bulk", headers=authorization_header(owner),
        json={"records": [{**base, "session_kind": "MORNING", "session_code": "MORNING"}, {**base, "session_kind": "EVENING", "session_code": "EVENING"}]},
    )
    assert valid.status_code == 201 and valid.json()["created"] == 2
    duplicate = client.post(
        f"/api/v1/farms/{farm.id}/milk/sessions/bulk", headers=authorization_header(owner),
        json={"records": [{**base, "milking_date": "2026-01-04", "session_kind": "MORNING", "session_code": "MORNING"}] * 2},
    )
    assert duplicate.status_code == 409
    assert db_session.scalar(select(func.count(MilkingSession.id))) == 2


def test_bulk_existing_conflict_rolls_back_entire_request(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    assert session(client, farm, owner, animal["id"], lac["id"]).status_code == 201
    records = [
        {"cattle_id": animal["id"], "lactation_id": lac["id"], "milking_date": "2026-01-02", "session_kind": "MORNING", "session_code": "MORNING", "volume_liters": "7"},
        {"cattle_id": animal["id"], "lactation_id": lac["id"], "milking_date": "2026-01-02", "session_kind": "EVENING", "session_code": "EVENING", "volume_liters": "7"},
    ]
    response = client.post(f"/api/v1/farms/{farm.id}/milk/sessions/bulk", headers=authorization_header(owner), json={"records": records})
    assert response.status_code == 409
    assert db_session.scalar(select(func.count(MilkingSession.id))) == 1


def test_correction_changes_analytics_without_mutating_original(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    milk = session(client, farm, owner, animal["id"], lac["id"]).json()
    response = client.post(
        f"/api/v1/farms/{farm.id}/milk/corrections", headers=authorization_header(owner),
        json={"cattle_id": animal["id"], "target_type": "SESSION", "target_id": milk["id"], "reason": "Scale transcription error", "replacement_values": {"volume_liters": "12.500"}},
    )
    assert response.status_code == 201
    original = db_session.get(MilkingSession, uuid.UUID(milk["id"]))
    assert str(original.volume_liters) == "10.250"
    summary = client.get(
        f"/api/v1/farms/{farm.id}/milk/analytics/production",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31", "interval": "daily"},
        headers=authorization_header(owner),
    )
    assert summary.status_code == 200
    assert summary.json()["total_volume_liters"] == "12.500"
    assert summary.json()["missing_records_are_zero"] is False


def test_daily_weekly_monthly_breakdown_and_empty_dataset(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    session(client, farm, owner, animal["id"], lac["id"])
    for interval in ("daily", "weekly", "monthly"):
        result = client.get(
            f"/api/v1/farms/{farm.id}/milk/analytics/production",
            params={"date_from": "2026-01-01", "date_to": "2026-01-31", "interval": interval},
            headers=authorization_header(owner),
        )
        assert result.status_code == 200 and result.json()["record_count"] == 1
    breakdown = client.get(
        f"/api/v1/farms/{farm.id}/milk/analytics/breakdown",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"}, headers=authorization_header(owner),
    )
    assert breakdown.status_code == 200 and breakdown.json()["highest_producing"]["cattle_id"] == animal["id"]
    empty = client.get(
        f"/api/v1/farms/{farm.id}/milk/analytics/production",
        params={"date_from": "2025-01-01", "date_to": "2025-01-02"}, headers=authorization_header(owner),
    )
    assert empty.json()["buckets"] == []


def test_dataset_contains_available_features_without_fabrication(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    session(client, farm, owner, animal["id"], lac["id"])
    data = client.get(
        f"/api/v1/farms/{farm.id}/milk/analytics/dataset",
        params={"date_from": "2026-01-01", "date_to": "2026-01-31"}, headers=authorization_header(owner),
    )
    assert data.status_code == 200
    assert data.json()[0]["observation_complete"] is False
    assert data.json()[0]["fat_percent"] is None


def test_cross_farm_object_guessing_and_history_isolation(client, db_session):
    owner_a, farm_a, _ = setup_farm(client, db_session, "farm-a")
    owner_b, farm_b, animal_b = setup_farm(client, db_session, "farm-b")
    lac = lactation(client, farm_b, owner_b, animal_b["id"]).json()
    milk = session(client, farm_b, owner_b, animal_b["id"], lac["id"]).json()
    assert client.get(f"/api/v1/farms/{farm_a.id}/milk/lactations/{lac['id']}", headers=authorization_header(owner_a)).status_code == 404
    assert client.get(f"/api/v1/farms/{farm_a.id}/milk/sessions/{milk['id']}", headers=authorization_header(owner_a)).status_code == 404
    assert client.get(f"/api/v1/farms/{farm_a.id}/milk/sessions", headers=authorization_header(owner_a)).json() == []


def test_worker_can_record_but_cannot_manage_or_correct(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    worker = create_user(db_session, email=f"worker-{uuid.uuid4().hex}@example.com")
    db_session.add(FarmMember(farm_id=farm.id, user_id=worker.id, role=FarmRole.WORKER, status=MemberStatus.ACTIVE))
    db_session.commit()
    milk = session(client, farm, worker, animal["id"], lac["id"])
    assert milk.status_code == 201
    assert lactation(client, farm, worker, animal["id"], 2).status_code == 403
    correction = client.post(
        f"/api/v1/farms/{farm.id}/milk/corrections", headers=authorization_header(worker),
        json={"cattle_id": animal["id"], "target_type": "SESSION", "target_id": milk.json()["id"], "reason": "Not allowed", "replacement_values": {"volume_liters": "1"}},
    )
    assert correction.status_code == 403


def test_manager_has_full_milk_management_and_vet_has_read_only(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    manager = create_user(db_session, email=f"manager-{uuid.uuid4().hex}@example.com")
    vet = create_user(db_session, email=f"vet-{uuid.uuid4().hex}@example.com")
    db_session.add_all([
        FarmMember(farm_id=farm.id, user_id=manager.id, role=FarmRole.FARM_MANAGER, status=MemberStatus.ACTIVE),
        FarmMember(farm_id=farm.id, user_id=vet.id, role=FarmRole.VETERINARIAN, status=MemberStatus.ACTIVE),
    ])
    db_session.commit()
    assert lactation(client, farm, manager, animal["id"]).status_code == 201
    assert client.get(f"/api/v1/farms/{farm.id}/milk/lactations", headers=authorization_header(vet)).status_code == 200
    assert lactation(client, farm, vet, animal["id"], 2).status_code == 403


def test_inactive_member_is_denied(client, db_session):
    owner, farm, _ = setup_farm(client, db_session)
    inactive = create_user(db_session, email=f"inactive-{uuid.uuid4().hex}@example.com")
    db_session.add(FarmMember(farm_id=farm.id, user_id=inactive.id, role=FarmRole.WORKER, status=MemberStatus.INACTIVE))
    db_session.commit()
    assert client.get(f"/api/v1/farms/{farm.id}/milk/sessions", headers=authorization_header(inactive)).status_code == 404


def test_finalized_cattle_blocks_new_records_but_history_remains(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()
    assert session(client, farm, owner, animal["id"], lac["id"]).status_code == 201
    transition = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{animal['id']}/lifecycle",
        headers=authorization_header(owner),
        json={"new_status": "SOLD", "effective_at": datetime.now(timezone.utc).isoformat(), "reason": "Sold"},
    )
    assert transition.status_code == 200
    assert session(client, farm, owner, animal["id"], lac["id"], milking_date="2026-01-03").status_code == 422
    assert len(client.get(f"/api/v1/farms/{farm.id}/milk/sessions", headers=authorization_header(owner)).json()) == 1



def test_dry_transition_rejects_date_before_existing_milking(
    client, db_session
):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()

    milk = session(
        client,
        farm,
        owner,
        animal["id"],
        lac["id"],
        milking_date="2026-01-15",
    )
    assert milk.status_code == 201

    response = client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations/{lac['id']}/transition",
        headers=authorization_header(owner),
        json={"status": "DRY", "effective_date": "2026-01-10"},
    )

    assert response.status_code == 422


def test_completion_rejects_date_before_dry_off(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()

    dry = client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations/{lac['id']}/transition",
        headers=authorization_header(owner),
        json={"status": "DRY", "effective_date": "2026-02-15"},
    )
    assert dry.status_code == 200

    completed = client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations/{lac['id']}/transition",
        headers=authorization_header(owner),
        json={"status": "COMPLETED", "effective_date": "2026-02-10"},
    )

    assert completed.status_code == 422


def test_lactation_transition_rejects_future_date(client, db_session):
    from datetime import timedelta
    from app.services.milk import utc_today

    owner, farm, animal = setup_farm(client, db_session)
    lac = lactation(client, farm, owner, animal["id"]).json()

    future_date = (utc_today() + timedelta(days=1)).isoformat()

    response = client.post(
        f"/api/v1/farms/{farm.id}/milk/lactations/{lac['id']}/transition",
        headers=authorization_header(owner),
        json={"status": "DRY", "effective_date": future_date},
    )

    assert response.status_code == 422
