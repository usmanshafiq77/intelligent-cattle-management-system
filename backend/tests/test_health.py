import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.cattle import Cattle
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.health import (
    HealthDiagnosis,
    HealthRecordCorrection,
    MedicationAdministration,
    TreatmentPlan,
    VaccinationAdministration,
    VaccinationSchedule,
)
from app.models.user import UserStatus
from tests.helpers import authorization_header, create_owned_farm, create_user
from tests.test_rbac import create_role


pytestmark = pytest.mark.integration
HOLSTEIN_ID = "15a83daf-5c4a-5cb9-8bed-5a4e7ea1e035"


def add_member(db, farm, user, role=FarmRole.WORKER, status=MemberStatus.ACTIVE):
    member = FarmMember(
        farm_id=farm.id, user_id=user.id, role=role, status=status
    )
    db.add(member)
    db.commit()
    return member


def register_animal(client, farm, owner, tag=None):
    response = client.post(
        f"/api/v1/farms/{farm.id}/cattle",
        headers=authorization_header(owner),
        json={
            "tag_number": tag or f"H-{uuid.uuid4().hex[:8]}",
            "species": "CATTLE",
            "sex": "FEMALE",
            "category": "COW",
            "breed_id": HOLSTEIN_ID,
            "date_of_birth": "2022-01-01",
        },
    )
    assert response.status_code == 201
    return response.json()


def setup_farm(client, db, suffix=None):
    suffix = suffix or uuid.uuid4().hex
    owner = create_user(db, email=f"health-{suffix}@example.com")
    farm = create_owned_farm(db, owner=owner, name=f"Health {suffix[:8]}")
    animal = register_animal(client, farm, owner)
    return owner, farm, animal


def create_encounter(client, farm, user, cattle_id, **overrides):
    payload = {
        "cattle_id": str(cattle_id),
        "encounter_type": "ILLNESS",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "symptoms": "Reduced appetite",
        "clinical_observations": "Alert and ambulatory",
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/farms/{farm.id}/health/encounters",
        headers=authorization_header(user),
        json=payload,
    )


def create_schedule(client, farm, user, cattle_id, **overrides):
    payload = {
        "cattle_id": cattle_id,
        "vaccine_name": "Farm-approved vaccine",
        "scheduled_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=7)).isoformat(),
    }
    payload.update(overrides)
    return client.post(
        f"/api/v1/farms/{farm.id}/health/vaccination-schedules",
        headers=authorization_header(user),
        json=payload,
    )


def test_encounter_diagnosis_related_records_and_animal_history(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    encounter = create_encounter(
        client, farm, owner, animal["id"], finalize=True
    )
    assert encounter.status_code == 201
    diagnosed_at = datetime.now(timezone.utc)
    diagnosis = client.post(
        f"/api/v1/farms/{farm.id}/health/diagnoses",
        headers=authorization_header(owner),
        json={
            "encounter_id": encounter.json()["id"],
            "condition_name": "Clinical condition",
            "severity": "MODERATE",
            "status": "SUSPECTED",
            "diagnosed_at": diagnosed_at.isoformat(),
            "clinical_signs": "Reduced appetite",
        },
    )
    assert diagnosis.status_code == 201
    assert diagnosis.json()["status"] == "SUSPECTED"
    transitioned = client.patch(
        f"/api/v1/farms/{farm.id}/health/diagnoses/{diagnosis.json()['id']}/status",
        headers=authorization_header(owner),
        json={"status": "CONFIRMED", "reason": "Laboratory result reviewed"},
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "CONFIRMED"

    related = client.get(
        f"/api/v1/farms/{farm.id}/health/encounters/{encounter.json()['id']}",
        headers=authorization_header(owner),
    )
    assert related.status_code == 200
    assert [item["id"] for item in related.json()["diagnoses"]] == [
        diagnosis.json()["id"]
    ]
    assert related.json()["diagnoses"][0]["status"] == "CONFIRMED"
    history = client.get(
        f"/api/v1/farms/{farm.id}/health/cattle/{animal['id']}/history",
        headers=authorization_header(owner),
    )
    assert history.status_code == 200
    assert len(history.json()["encounters"]) == 1
    assert len(history.json()["diagnoses"]) == 1


def test_encounter_rejects_invalid_and_cross_farm_cattle(client, db_session):
    owner_a, farm_a, _ = setup_farm(client, db_session, "cross-a")
    owner_b, _, animal_b = setup_farm(client, db_session, "cross-b")
    cross = create_encounter(client, farm_a, owner_a, animal_b["id"])
    assert cross.status_code == 404
    missing = create_encounter(client, farm_a, owner_a, uuid.uuid4())
    assert missing.status_code == 404
    assert owner_b.id


def test_encounter_chronology_and_pagination_filters(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    future = create_encounter(
        client,
        farm,
        owner,
        animal["id"],
        occurred_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    )
    assert future.status_code == 422
    for kind in ("ROUTINE", "INJURY"):
        assert create_encounter(
            client, farm, owner, animal["id"], encounter_type=kind
        ).status_code == 201
    page = client.get(
        f"/api/v1/farms/{farm.id}/health/encounters",
        headers=authorization_header(owner),
        params={"limit": 1, "offset": 1},
    )
    assert page.status_code == 200
    assert len(page.json()) == 1
    filtered = client.get(
        f"/api/v1/farms/{farm.id}/health/encounters",
        headers=authorization_header(owner),
        params={"encounter_type": "INJURY"},
    )
    assert len(filtered.json()) == 1


def test_health_routes_require_authentication_and_valid_tokens(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    url = f"/api/v1/farms/{farm.id}/health/encounters"
    assert client.get(url).status_code == 401
    invalid = client.get(url, headers={"Authorization": "Bearer invalid"})
    assert invalid.status_code == 401
    malformed = client.get(
        f"/api/v1/farms/not-a-uuid/health/encounters",
        headers=authorization_header(owner),
    )
    assert malformed.status_code == 422
    assert animal["id"]


def test_worker_is_read_only_and_custom_role_can_create_encounter(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    worker = create_user(db_session, email=f"worker-{uuid.uuid4().hex}@example.com")
    membership = add_member(db_session, farm, worker)
    assert create_encounter(client, farm, worker, animal["id"]).status_code == 403
    assert client.get(
        f"/api/v1/farms/{farm.id}/health/encounters",
        headers=authorization_header(worker),
    ).status_code == 200
    role_id = create_role(
        client,
        owner,
        farm,
        name="Health Recorder",
        permissions=["health.manage"],
    ).json()["id"]
    assigned = client.post(
        f"/api/v1/farms/{farm.id}/staff/{membership.id}/roles",
        headers=authorization_header(owner),
        json={"role_ids": [role_id]},
    )
    assert assigned.status_code == 200
    assert create_encounter(client, farm, worker, animal["id"]).status_code == 201


@pytest.mark.parametrize("inactive_kind", ["membership", "user"])
def test_inactive_principal_cannot_access_health(
    client, db_session, inactive_kind
):
    owner, farm, _ = setup_farm(client, db_session)
    user = create_user(
        db_session,
        email=f"inactive-{uuid.uuid4().hex}@example.com",
        status=(
            UserStatus.INACTIVE
            if inactive_kind == "user"
            else UserStatus.ACTIVE
        ),
    )
    add_member(
        db_session,
        farm,
        user,
        FarmRole.VETERINARIAN,
        MemberStatus.INACTIVE
        if inactive_kind == "membership"
        else MemberStatus.ACTIVE,
    )
    response = client.get(
        f"/api/v1/farms/{farm.id}/health/encounters",
        headers=authorization_header(user),
    )
    assert response.status_code in {401, 403, 404}
    assert owner.id


def test_vaccination_schedule_reschedule_cancel_and_history(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    schedule = create_schedule(client, farm, owner, animal["id"])
    assert schedule.status_code == 201
    updated = client.patch(
        f"/api/v1/farms/{farm.id}/health/vaccination-schedules/{schedule.json()['id']}",
        headers=authorization_header(owner),
        json={
            "scheduled_date": (date.today() + timedelta(days=1)).isoformat(),
            "due_date": (date.today() + timedelta(days=8)).isoformat(),
            "reason": "Veterinarian availability changed",
        },
    )
    assert updated.status_code == 200
    cancelled = client.patch(
        f"/api/v1/farms/{farm.id}/health/vaccination-schedules/{schedule.json()['id']}",
        headers=authorization_header(owner),
        json={"status": "CANCELLED", "reason": "Plan replaced"},
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert db_session.scalar(select(func.count(HealthRecordCorrection.id))) == 2


def test_vaccination_administration_completes_schedule_and_prevents_duplicate(
    client, db_session
):
    owner, farm, animal = setup_farm(client, db_session)
    schedule = create_schedule(
        client,
        farm,
        owner,
        animal["id"],
        due_date=date.today().isoformat(),
    ).json()
    payload = {
        "cattle_id": animal["id"],
        "schedule_id": schedule["id"],
        "vaccine_name": schedule["vaccine_name"],
        "administered_at": datetime.now(timezone.utc).isoformat(),
        "dose": "2.5",
        "dose_unit": "mL",
        "batch_lot_number": "LOT-17",
    }
    url = f"/api/v1/farms/{farm.id}/health/vaccination-administrations"
    first = client.post(url, headers=authorization_header(owner), json=payload)
    assert first.status_code == 201
    assert client.post(
        url, headers=authorization_header(owner), json=payload
    ).status_code == 409
    schedules = client.get(
        f"/api/v1/farms/{farm.id}/health/vaccination-schedules",
        headers=authorization_header(owner),
    ).json()
    assert schedules[0]["status"] == "COMPLETED"
    assert db_session.scalar(
        select(func.count(VaccinationAdministration.id))
    ) == 1


def test_vaccination_rejects_cross_farm_schedule_reference(client, db_session):
    owner_a, farm_a, animal_a = setup_farm(client, db_session, "vac-a")
    owner_b, farm_b, animal_b = setup_farm(client, db_session, "vac-b")
    schedule_b = create_schedule(
        client, farm_b, owner_b, animal_b["id"]
    ).json()
    response = client.post(
        f"/api/v1/farms/{farm_a.id}/health/vaccination-administrations",
        headers=authorization_header(owner_a),
        json={
            "cattle_id": animal_a["id"],
            "schedule_id": schedule_b["id"],
            "vaccine_name": schedule_b["vaccine_name"],
            "administered_at": datetime.now(timezone.utc).isoformat(),
            "dose": "1",
            "dose_unit": "mL",
        },
    )
    assert response.status_code == 404


def test_standalone_vaccination_replay_is_rejected(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    payload = {
        "cattle_id": animal["id"],
        "vaccine_name": "Standalone vaccine",
        "administered_at": datetime.now(timezone.utc).isoformat(),
        "dose": "1",
        "dose_unit": "mL",
        "batch_lot_number": "STANDALONE-17",
    }
    url = f"/api/v1/farms/{farm.id}/health/vaccination-administrations"
    assert client.post(
        url, headers=authorization_header(owner), json=payload
    ).status_code == 201
    assert client.post(
        url, headers=authorization_header(owner), json=payload
    ).status_code == 409


def test_overdue_vaccination_reminder_is_deterministic(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    assert create_schedule(
        client,
        farm,
        owner,
        animal["id"],
        scheduled_date="2026-01-01",
        due_date="2026-01-02",
    ).status_code == 201
    response = client.get(
        f"/api/v1/farms/{farm.id}/health/reminders",
        headers=authorization_header(owner),
        params={"as_of": "2026-02-01T00:00:00+00:00"},
    )
    assert response.status_code == 200
    assert response.json()[0]["kind"] == "VACCINATION_OVERDUE"
    assert response.json()[0]["overdue"] is True


def test_follow_up_reminders_include_horizon_boundary_and_exclude_outside(
    client,
    db_session,
):
    owner, farm, animal = setup_farm(client, db_session)
    occurred = datetime.now(timezone.utc)
    as_of = occurred + timedelta(days=2)

    for suffix, due in (
        ("past", occurred + timedelta(days=1)),
        ("tomorrow", as_of + timedelta(days=1)),
        ("boundary", as_of + timedelta(days=2)),
        ("outside", as_of + timedelta(days=2, seconds=1)),
    ):
        response = create_encounter(
            client,
            farm,
            owner,
            animal["id"],
            occurred_at=occurred.isoformat(),
            symptoms=suffix,
            follow_up_due_at=due.isoformat(),
        )
        assert response.status_code == 201

    reminders = client.get(
        f"/api/v1/farms/{farm.id}/health/reminders",
        headers=authorization_header(owner),
        params={"as_of": as_of.isoformat(), "horizon_days": 2},
    )
    assert reminders.status_code == 200
    followups = [
        item
        for item in reminders.json()
        if item["kind"].startswith("FOLLOW_UP_")
    ]
    assert [item["kind"] for item in followups] == [
        "FOLLOW_UP_OVERDUE",
        "FOLLOW_UP_UPCOMING",
        "FOLLOW_UP_UPCOMING",
    ]
    assert [item["overdue"] for item in followups] == [True, False, False]


def test_terminal_cattle_do_not_produce_actionable_health_reminders(
    client,
    db_session,
):
    owner, farm, animal = setup_farm(client, db_session)
    occurred = datetime.now(timezone.utc)
    due = occurred + timedelta(days=1)
    encounter = create_encounter(
        client,
        farm,
        owner,
        animal["id"],
        occurred_at=occurred.isoformat(),
        follow_up_due_at=due.isoformat(),
    )
    assert encounter.status_code == 201
    sold = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{animal['id']}/lifecycle",
        headers=authorization_header(owner),
        json={
            "new_status": "SOLD",
            "effective_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert sold.status_code == 200

    reminders = client.get(
        f"/api/v1/farms/{farm.id}/health/reminders",
        headers=authorization_header(owner),
        params={"as_of": datetime.now(timezone.utc).isoformat()},
    )
    assert reminders.status_code == 200
    assert reminders.json() == []


def test_treatment_medication_completion_and_audit_history(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    treatment = client.post(
        f"/api/v1/farms/{farm.id}/health/treatments",
        headers=authorization_header(owner),
        json={
            "cattle_id": animal["id"],
            "name": "Supportive treatment",
            "medication_name": "Prescribed medicine",
            "dosage_quantity": "5",
            "dosage_unit": "mL",
            "start_date": date.today().isoformat(),
            "withdrawal_period_days": 0,
        },
    )
    assert treatment.status_code == 201
    medication = client.post(
        f"/api/v1/farms/{farm.id}/health/treatments/{treatment.json()['id']}/medication-administrations",
        headers=authorization_header(owner),
        json={
            "administered_at": datetime.now(timezone.utc).isoformat(),
            "medication_name": "Prescribed medicine",
            "quantity": "5",
            "unit": "mL",
        },
    )
    assert medication.status_code == 201
    completed = client.post(
        f"/api/v1/farms/{farm.id}/health/treatments/{treatment.json()['id']}/transition",
        headers=authorization_header(owner),
        json={"status": "COMPLETED", "reason": "Course completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert db_session.scalar(
        select(func.count(MedicationAdministration.id))
    ) == 1
    assert db_session.scalar(select(func.count(HealthRecordCorrection.id))) == 2


def test_treatment_invalid_transition_and_dose_validation(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    invalid_dose = client.post(
        f"/api/v1/farms/{farm.id}/health/treatments",
        headers=authorization_header(owner),
        json={
            "cattle_id": animal["id"],
            "name": "Invalid",
            "dosage_quantity": "0",
            "dosage_unit": "mL",
            "start_date": date.today().isoformat(),
        },
    )
    assert invalid_dose.status_code == 422
    treatment = client.post(
        f"/api/v1/farms/{farm.id}/health/treatments",
        headers=authorization_header(owner),
        json={
            "cattle_id": animal["id"],
            "name": "Planned",
            "start_date": date.today().isoformat(),
        },
    ).json()
    invalid = client.post(
        f"/api/v1/farms/{farm.id}/health/treatments/{treatment['id']}/transition",
        headers=authorization_header(owner),
        json={"status": "COMPLETED", "reason": "Invalid shortcut"},
    )
    assert invalid.status_code == 422


def test_veterinary_visit_schedule_complete_and_follow_up_reminder(
    client, db_session
):
    owner, farm, animal = setup_farm(client, db_session)
    planned = datetime.now(timezone.utc) + timedelta(days=1)
    visit = client.post(
        f"/api/v1/farms/{farm.id}/health/veterinary-visits",
        headers=authorization_header(owner),
        json={
            "cattle_id": animal["id"],
            "planned_at": planned.isoformat(),
            "reason": "Routine examination",
        },
    )
    assert visit.status_code == 201
    actual = datetime.now(timezone.utc)
    completed = client.patch(
        f"/api/v1/farms/{farm.id}/health/veterinary-visits/{visit.json()['id']}",
        headers=authorization_header(owner),
        json={
            "status": "COMPLETED",
            "actual_at": actual.isoformat(),
            "follow_up_due_at": (actual + timedelta(days=2)).isoformat(),
            "clinical_notes": "Exam completed",
            "reason": "Visit completed",
        },
    )
    assert completed.status_code == 200
    reminders = client.get(
        f"/api/v1/farms/{farm.id}/health/reminders",
        headers=authorization_header(owner),
        params={
            "as_of": (actual + timedelta(days=3)).isoformat(),
            "horizon_days": 30,
        },
    )
    assert any(x["kind"] == "FOLLOW_UP_OVERDUE" for x in reminders.json())


def test_veterinary_visit_rejects_invalid_state_transition(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    visit = client.post(
        f"/api/v1/farms/{farm.id}/health/veterinary-visits",
        headers=authorization_header(owner),
        json={"cattle_id": animal["id"], "reason": "Requested consultation"},
    ).json()
    response = client.patch(
        f"/api/v1/farms/{farm.id}/health/veterinary-visits/{visit['id']}",
        headers=authorization_header(owner),
        json={
            "status": "COMPLETED",
            "actual_at": datetime.now(timezone.utc).isoformat(),
            "reason": "Invalid direct completion",
        },
    )
    assert response.status_code == 422


def test_correction_preserves_original_record_and_audit_is_restricted(
    client, db_session
):
    owner, farm, animal = setup_farm(client, db_session)
    encounter = create_encounter(client, farm, owner, animal["id"]).json()
    correction = client.post(
        f"/api/v1/farms/{farm.id}/health/corrections",
        headers=authorization_header(owner),
        json={
            "cattle_id": animal["id"],
            "record_type": "ENCOUNTER",
            "record_id": encounter["id"],
            "reason": "Clarify observation",
            "correction_note": "The observation should be read with context.",
            "replacement_data": {"clinical_observations": "Clarified"},
        },
    )
    assert correction.status_code == 201
    original = client.get(
        f"/api/v1/farms/{farm.id}/health/encounters/{encounter['id']}",
        headers=authorization_header(owner),
    ).json()["encounter"]
    assert original["clinical_observations"] == "Alert and ambulatory"
    worker = create_user(db_session, email=f"audit-{uuid.uuid4().hex}@example.com")
    add_member(db_session, farm, worker)
    denied = client.get(
        f"/api/v1/farms/{farm.id}/health/corrections",
        headers=authorization_header(worker),
    )
    assert denied.status_code == 403


def test_direct_object_guessing_never_discloses_other_farm_health_records(
    client, db_session
):
    owner_a, farm_a, _ = setup_farm(client, db_session, "guess-a")
    owner_b, farm_b, animal_b = setup_farm(client, db_session, "guess-b")
    encounter_b = create_encounter(
        client, farm_b, owner_b, animal_b["id"]
    ).json()
    response = client.get(
        f"/api/v1/farms/{farm_a.id}/health/encounters/{encounter_b['id']}",
        headers=authorization_header(owner_a),
    )
    assert response.status_code == 404


def test_health_transaction_rolls_back_duplicate_medication_event(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    treatment = TreatmentPlan(
        farm_id=farm.id,
        cattle_id=uuid.UUID(animal["id"]),
        name="Database treatment",
        start_date=date.today(),
        status="ACTIVE",
        created_by_id=owner.id,
    )
    db_session.add(treatment)
    db_session.commit()
    timestamp = datetime.now(timezone.utc)
    payload = {
        "administered_at": timestamp.isoformat(),
        "medication_name": "Medicine",
        "quantity": "1",
        "unit": "mL",
    }
    url = f"/api/v1/farms/{farm.id}/health/treatments/{treatment.id}/medication-administrations"
    assert client.post(
        url, headers=authorization_header(owner), json=payload
    ).status_code == 201
    assert client.post(
        url, headers=authorization_header(owner), json=payload
    ).status_code == 409
    assert db_session.scalar(
        select(func.count(MedicationAdministration.id)).where(
            MedicationAdministration.treatment_id == treatment.id
        )
    ) == 1


def test_finalized_cattle_blocks_new_actions_but_history_remains_readable(
    client, db_session
):
    owner, farm, animal = setup_farm(client, db_session)
    encounter = create_encounter(client, farm, owner, animal["id"])
    assert encounter.status_code == 201
    transition = client.post(
        f"/api/v1/farms/{farm.id}/cattle/{animal['id']}/lifecycle",
        headers=authorization_header(owner),
        json={
            "new_status": "SOLD",
            "effective_at": datetime.now(timezone.utc).isoformat(),
            "reason": "Transferred ownership",
        },
    )
    assert transition.status_code == 200
    assert create_encounter(client, farm, owner, animal["id"]).status_code == 422
    history = client.get(
        f"/api/v1/farms/{farm.id}/health/cattle/{animal['id']}/history",
        headers=authorization_header(owner),
    )
    assert history.status_code == 200
    assert len(history.json()["encounters"]) == 1


def test_health_seed_catalog_and_model_rows_are_present(client, db_session):
    owner, farm, animal = setup_farm(client, db_session)
    assert create_schedule(client, farm, owner, animal["id"]).status_code == 201
    assert db_session.scalar(select(func.count(VaccinationSchedule.id))) == 1
    assert db_session.scalar(select(func.count(Cattle.id))) == 1
    assert db_session.scalar(select(func.count(HealthDiagnosis.id))) == 0
