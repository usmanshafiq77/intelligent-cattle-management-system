import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.breeding import BreedingAuditEvent, CalvingOffspring
from app.models.cattle import AnimalCategory, AnimalSex, Cattle, Species
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from tests.helpers import authorization_header, create_owned_farm, create_user


pytestmark = pytest.mark.integration


def setup(db, suffix=None):
    suffix = suffix or uuid.uuid4().hex[:8]
    owner = create_user(db, email=f"breed-owner-{suffix}@example.com")
    farm = create_owned_farm(db, owner=owner, name=f"Breeding Farm {suffix}")
    cow = Cattle(farm_id=farm.id, tag_number=f"COW-{suffix}", normalized_tag=f"cow-{suffix}", species=Species.CATTLE, sex=AnimalSex.FEMALE, category=AnimalCategory.COW, date_of_birth=date(2022, 1, 1), created_by_id=owner.id)
    bull = Cattle(farm_id=farm.id, tag_number=f"BULL-{suffix}", normalized_tag=f"bull-{suffix}", species=Species.CATTLE, sex=AnimalSex.MALE, category=AnimalCategory.BULL, date_of_birth=date(2021, 1, 1), created_by_id=owner.id)
    db.add_all([cow, bull]); db.commit()
    return owner, farm, cow, bull


def member(db, farm, role):
    user = create_user(db, email=f"breed-{role.value.lower()}-{uuid.uuid4().hex[:8]}@example.com")
    db.add(FarmMember(farm_id=farm.id, user_id=user.id, role=role, status=MemberStatus.ACTIVE)); db.commit()
    return user


def heat(client, farm, actor, cow, request_id=None):
    return client.post(f"/api/v1/farms/{farm.id}/breeding/heat-observations", headers=authorization_header(actor), json={"client_request_id": str(request_id or uuid.uuid4()), "cattle_id": str(cow.id), "observed_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), "signs": "Standing heat and restlessness", "intensity": "MODERATE", "cycle_length_days": 21, "create_reminder": True})


def event(client, farm, actor, cow, bull, request_id=None):
    moment = datetime.now(timezone.utc) - timedelta(days=35)
    return client.post(f"/api/v1/farms/{farm.id}/breeding/events", headers=authorization_header(actor), json={"client_request_id": str(request_id or uuid.uuid4()), "cow_id": str(cow.id), "sire_id": str(bull.id), "method": "NATURAL_MATING", "status": "COMPLETED", "scheduled_at": moment.isoformat(), "completed_at": moment.isoformat(), "follow_up_due_at": (moment + timedelta(days=30)).isoformat()})


def test_heat_observation_estimate_worker_rbac_and_duplicate_protection(client, db_session):
    owner, farm, cow, bull = setup(db_session)
    worker = member(db_session, farm, FarmRole.WORKER)
    request_id = uuid.uuid4()
    response = heat(client, farm, worker, cow, request_id)
    assert response.status_code == 201
    assert response.json()["estimated_next_heat_at"]
    assert "not a clinical confirmation" in response.json()["estimate_disclaimer"]
    assert heat(client, farm, worker, cow, request_id).status_code == 409
    assert heat(client, farm, worker, bull).status_code == 422
    reminders = client.get(f"/api/v1/farms/{farm.id}/breeding/reminders", headers=authorization_header(worker))
    assert reminders.status_code == 200
    assert reminders.json()[0]["is_estimate"] is True


def test_breeding_event_does_not_infer_pregnancy_and_validates_farm(client, db_session):
    owner, farm, cow, bull = setup(db_session)
    created = event(client, farm, owner, cow, bull)
    assert created.status_code == 201
    assert "does not confirm conception" in created.json()["conception_disclaimer"]
    other_owner, other_farm, _, other_bull = setup(db_session)
    cross = event(client, farm, owner, cow, other_bull)
    assert cross.status_code == 422
    assert client.get(f"/api/v1/farms/{other_farm.id}/breeding/events", headers=authorization_header(other_owner)).json() == []


def test_only_veterinarian_can_sign_pregnancy_assessment_and_expected_date_is_estimate(client, db_session):
    owner, farm, cow, bull = setup(db_session)
    vet = member(db_session, farm, FarmRole.VETERINARIAN)
    breeding = event(client, farm, owner, cow, bull).json()
    payload = {"client_request_id": str(uuid.uuid4()), "cattle_id": str(cow.id), "breeding_event_id": breeding["id"], "examined_at": datetime.now(timezone.utc).isoformat(), "assessment": "PREGNANT", "clinical_assessment": "Positive pregnancy assessment by ultrasound", "calculate_expected_calving": True, "gestation_days_used": 283}
    assert client.post(f"/api/v1/farms/{farm.id}/breeding/pregnancy-examinations", headers=authorization_header(owner), json=payload).status_code == 403
    response = client.post(f"/api/v1/farms/{farm.id}/breeding/pregnancy-examinations", headers=authorization_header(vet), json=payload)
    assert response.status_code == 201
    assert response.json()["examined_by_id"] == str(vet.id)
    assert response.json()["expected_calving_date"]
    assert "estimates" in response.json()["estimate_disclaimer"]
    payload["client_request_id"] = str(uuid.uuid4())
    payload["assessment"] = "NOT_PREGNANT"
    payload["calculate_expected_calving"] = True
    assert client.post(f"/api/v1/farms/{farm.id}/breeding/pregnancy-examinations", headers=authorization_header(vet), json=payload).status_code == 422


def test_worker_factual_calving_vet_clinical_signature_and_no_overwrite(client, db_session):
    owner, farm, cow, _ = setup(db_session)
    worker = member(db_session, farm, FarmRole.WORKER)
    vet = member(db_session, farm, FarmRole.VETERINARIAN)
    payload = {"client_request_id": str(uuid.uuid4()), "dam_id": str(cow.id), "calved_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(), "outcome": "LIVE_BIRTH", "delivery_type": "ASSISTED", "calf_count": 1, "live_count": 1, "stillborn_count": 0, "factual_observations": "One live calf observed", "assistance_details": "Worker assisted positioning"}
    created = client.post(f"/api/v1/farms/{farm.id}/breeding/calvings", headers=authorization_header(worker), json=payload)
    assert created.status_code == 201
    clinical_url = f"/api/v1/farms/{farm.id}/breeding/calvings/{created.json()['id']}/clinical"
    clinical = {"clinical_complications": "Mild retained membrane risk; monitor", "clinical_diagnosis": "Post-calving monitoring required", "post_calving_follow_up_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}
    assert client.patch(clinical_url, headers=authorization_header(worker), json=clinical).status_code == 403
    assert client.patch(clinical_url, headers=authorization_header(vet), json=clinical).status_code == 200
    assert client.patch(clinical_url, headers=authorization_header(vet), json=clinical).status_code == 409


def test_offspring_registration_is_atomic_and_prevents_duplicates(client, db_session):
    owner, farm, cow, bull = setup(db_session)
    breeding = event(client, farm, owner, cow, bull).json()
    calving = client.post(f"/api/v1/farms/{farm.id}/breeding/calvings", headers=authorization_header(owner), json={"client_request_id": str(uuid.uuid4()), "dam_id": str(cow.id), "breeding_event_id": breeding["id"], "calved_at": datetime.now(timezone.utc).isoformat(), "outcome": "LIVE_BIRTH", "delivery_type": "NORMAL", "calf_count": 1, "live_count": 1, "stillborn_count": 0}).json()
    payload = {"client_request_id": str(uuid.uuid4()), "tag_number": f"CALF-{uuid.uuid4().hex[:5]}", "name": "Newborn", "sex": "FEMALE", "species": "CATTLE", "category": "CALF", "birth_weight_kg": "32.5", "birth_order": 1}
    response = client.post(f"/api/v1/farms/{farm.id}/breeding/calvings/{calving['id']}/offspring", headers=authorization_header(owner), json=payload)
    assert response.status_code == 201
    calf = db_session.get(Cattle, uuid.UUID(response.json()["cattle_id"]))
    assert calf.mother_id == cow.id and calf.father_id == bull.id
    assert db_session.scalar(select(func.count(CalvingOffspring.id))) == 1
    duplicate = dict(payload, tag_number="ANOTHER-CALF", client_request_id=str(uuid.uuid4()))
    assert client.post(f"/api/v1/farms/{farm.id}/breeding/calvings/{calving['id']}/offspring", headers=authorization_header(owner), json=duplicate).status_code == 409
    assert db_session.scalar(select(func.count(CalvingOffspring.id))) == 1


def test_parentage_cycle_sex_and_cross_farm_validation(client, db_session):
    owner, farm, cow, bull = setup(db_session)
    calf = Cattle(farm_id=farm.id, tag_number="PED-CALF", normalized_tag="ped-calf", species=Species.CATTLE, sex=AnimalSex.FEMALE, category=AnimalCategory.CALF, created_by_id=owner.id)
    db_session.add(calf); db_session.commit()
    url = f"/api/v1/farms/{farm.id}/breeding/parentage"
    accepted = client.post(url, headers=authorization_header(owner), json={"client_request_id": str(uuid.uuid4()), "child_id": str(calf.id), "parent_id": str(cow.id), "parent_role": "DAM", "status": "DOCUMENT_VERIFIED", "confidence_percent": "90"})
    assert accepted.status_code == 201
    wrong_sex = client.post(url, headers=authorization_header(owner), json={"client_request_id": str(uuid.uuid4()), "child_id": str(calf.id), "parent_id": str(cow.id), "parent_role": "SIRE", "status": "REPORTED"})
    assert wrong_sex.status_code == 422
    cycle = client.post(url, headers=authorization_header(owner), json={"client_request_id": str(uuid.uuid4()), "child_id": str(cow.id), "parent_id": str(calf.id), "parent_role": "DAM", "status": "REPORTED"})
    assert cycle.status_code == 422
    _, _, _, other_bull = setup(db_session)
    cross = client.post(url, headers=authorization_header(owner), json={"client_request_id": str(uuid.uuid4()), "child_id": str(calf.id), "parent_id": str(other_bull.id), "parent_role": "SIRE", "status": "REPORTED"})
    assert cross.status_code == 422
    pedigree = client.get(f"/api/v1/farms/{farm.id}/breeding/pedigree/{calf.id}", headers=authorization_header(owner))
    assert pedigree.status_code == 200
    assert any(node["relationship"] == "DAM" for node in pedigree.json()["ancestors"])
    assert "unknown or unverified" in pedigree.json()["limitation"]


def test_reports_dashboard_audit_and_system_admin_isolation(client, db_session):
    owner, farm, cow, _ = setup(db_session)
    heat(client, farm, owner, cow)
    dashboard = client.get(f"/api/v1/farms/{farm.id}/breeding/dashboard", headers=authorization_header(owner))
    assert dashboard.status_code == 200 and dashboard.json()["heat_observations"] == 1
    report = client.get(f"/api/v1/farms/{farm.id}/breeding/reports/summary", headers=authorization_header(owner), params={"date_from": date.today().isoformat(), "date_to": date.today().isoformat()})
    assert report.status_code == 200 and "data_note" in report.json()
    audit = client.get(f"/api/v1/farms/{farm.id}/breeding/audit", headers=authorization_header(owner))
    assert audit.status_code == 200 and len(audit.json()) >= 1
    assert db_session.scalar(select(func.count(BreedingAuditEvent.id))) >= 1
    admin = create_user(db_session, email=f"breed-admin-{uuid.uuid4().hex[:8]}@example.com")
    admin.is_system_admin = True; db_session.commit()
    assert client.get(f"/api/v1/farms/{farm.id}/breeding/dashboard", headers=authorization_header(admin)).status_code == 404
