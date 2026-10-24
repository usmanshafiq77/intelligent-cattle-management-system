import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.cattle import AnimalCategory, AnimalSex, Cattle, CattleStatus, Species
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.work_management import AppNotification
from app.services.work_reminders import generate_due_task_notifications
from tests.helpers import authorization_header, create_owned_farm, create_user

pytestmark = pytest.mark.integration


def setup_farm(db):
    suffix = uuid.uuid4().hex[:8]
    owner = create_user(db, email=f"task-owner-{suffix}@example.com")
    farm = create_owned_farm(db, owner=owner, name=f"Task Farm {suffix}")
    worker = create_user(db, email=f"task-worker-{suffix}@example.com")
    other = create_user(db, email=f"task-other-{suffix}@example.com")
    db.add(FarmMember(farm_id=farm.id, user_id=worker.id, role=FarmRole.WORKER, status=MemberStatus.ACTIVE))
    animal = Cattle(farm_id=farm.id, tag_number=f"T-{suffix}", normalized_tag=f"t-{suffix}", name="Task Cow", species=Species.CATTLE, sex=AnimalSex.FEMALE, category=AnimalCategory.COW, status=CattleStatus.ACTIVE, created_by_id=owner.id)
    db.add(animal); db.commit()
    return owner, worker, other, farm, animal


def test_task_assignment_status_notification_and_idempotency(client, db_session):
    owner, worker, _, farm, animal = setup_farm(db_session)
    request_id = str(uuid.uuid4())
    payload = {"title": "Check water trough", "description": "Verify and clean", "category": "GENERAL", "priority": "HIGH", "due_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(), "cattle_id": str(animal.id), "assignee_ids": [str(worker.id)], "recurrence_kind": "NONE", "recurrence_interval": 1, "client_request_id": request_id}
    first = client.post(f"/api/v1/farms/{farm.id}/work/tasks", headers=authorization_header(owner), json=payload)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/farms/{farm.id}/work/tasks", headers=authorization_header(owner), json=payload)
    assert second.status_code == 201 and second.json()["id"] == first.json()["id"]
    mine = client.get(f"/api/v1/farms/{farm.id}/work/tasks", headers=authorization_header(worker)).json()
    assert [row["id"] for row in mine] == [first.json()["id"]]
    started = client.post(f"/api/v1/farms/{farm.id}/work/tasks/{first.json()['id']}/status", headers=authorization_header(worker), json={"status": "IN_PROGRESS", "expected_version": 1})
    assert started.status_code == 200 and started.json()["version"] == 2
    stale = client.post(f"/api/v1/farms/{farm.id}/work/tasks/{first.json()['id']}/status", headers=authorization_header(worker), json={"status": "COMPLETED", "expected_version": 1})
    assert stale.status_code == 409
    inbox = client.get("/api/v1/notifications", headers=authorization_header(worker))
    assert inbox.status_code == 200 and inbox.json()["unread"] == 1
    assert generate_due_task_notifications(db_session) == 1
    assert generate_due_task_notifications(db_session) == 0
    assert len(db_session.scalars(select(AppNotification).where(AppNotification.user_id == worker.id)).all()) == 2


def test_farm_isolation_rbac_and_worker_cattle_assignment(client, db_session):
    owner, worker, other, farm, animal = setup_farm(db_session)
    denied = client.post(f"/api/v1/farms/{farm.id}/work/tasks", headers=authorization_header(worker), json={"title": "Forbidden", "category": "GENERAL", "priority": "LOW", "assignee_ids": [], "recurrence_kind": "NONE", "recurrence_interval": 1, "client_request_id": str(uuid.uuid4())})
    assert denied.status_code == 403
    hidden = client.get(f"/api/v1/farms/{farm.id}/work/tasks", headers=authorization_header(other))
    assert hidden.status_code == 404
    assigned = client.post(f"/api/v1/farms/{farm.id}/work/cattle-assignments", headers=authorization_header(owner), json={"worker_id": str(worker.id), "cattle_id": str(animal.id)})
    assert assigned.status_code == 201, assigned.text
    mine = client.get(f"/api/v1/farms/{farm.id}/work/cattle-assignments", headers=authorization_header(worker))
    assert mine.status_code == 200 and mine.json()[0]["cattle_id"] == str(animal.id)
    inbox = client.get("/api/v1/notifications", headers=authorization_header(worker), params={"farm_id": str(farm.id)})
    assert inbox.status_code == 200 and inbox.json()["items"][0]["category"] == "CATTLE_ASSIGNMENT"
    ended = client.delete(f"/api/v1/farms/{farm.id}/work/cattle-assignments/{assigned.json()['id']}", headers=authorization_header(owner))
    assert ended.status_code == 204
    assert client.get(f"/api/v1/farms/{farm.id}/work/cattle-assignments", headers=authorization_header(worker)).json() == []
