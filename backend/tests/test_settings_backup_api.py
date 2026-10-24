import pytest
from sqlalchemy import select

from app.models.settings_backup import PendingEmailChange, SecurityEvent
from tests.helpers import authorization_header, create_owned_farm, create_user


pytestmark = pytest.mark.integration


def test_profile_preferences_password_and_token_revocation(client, db_session):
    user = create_user(db_session, email="settings-user@example.com")
    headers = authorization_header(user)
    updated = client.patch("/api/v1/auth/me", headers=headers, json={"full_name": "Updated User"})
    assert updated.status_code == 200 and updated.json()["full_name"] == "Updated User"
    preferences = client.put("/api/v1/auth/me/preferences", headers=headers, json={"phone": "+92 300 1234567", "language": "en", "timezone": "Asia/Karachi", "date_format": "DD/MM/YYYY", "time_format": "12H", "theme": "midnight"})
    assert preferences.status_code == 200 and preferences.json()["timezone"] == "Asia/Karachi"
    changed = client.post("/api/v1/auth/me/change-password", headers=headers, json={"current_password": "ValidPassword123!", "new_password": "New!Password456"})
    assert changed.status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_email_change_requires_verification_and_revokes_sessions(client, db_session, memory_email_sender):
    user = create_user(db_session, email="old-address@example.com")
    headers = authorization_header(user)
    requested = client.post("/api/v1/auth/me/email-change", headers=headers, json={"new_email": "new-address@example.com", "current_password": "ValidPassword123!"})
    assert requested.status_code == 202
    db_session.refresh(user); assert user.email == "old-address@example.com"
    assert db_session.scalar(select(PendingEmailChange).where(PendingEmailChange.user_id == user.id)) is not None
    verified = client.post("/api/v1/auth/verify-email", json={"token": memory_email_sender.messages[-1].token})
    assert verified.status_code == 200
    db_session.refresh(user); assert user.email == "new-address@example.com" and user.email_verified_at is not None
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_farm_preferences_are_permission_scoped(client, db_session):
    owner = create_user(db_session, email="settings-owner@example.com"); farm = create_owned_farm(db_session, owner=owner); headers = authorization_header(owner)
    response = client.put(f"/api/v1/farms/{farm.id}/settings", headers=headers, json={"contact_email": "farm@example.com", "timezone": "Asia/Karachi", "measurement_system": "METRIC", "milk_volume_unit": "LITER", "feed_weight_unit": "KG", "notification_settings": {"tasks": True}, "operational_settings": {}})
    assert response.status_code == 200 and response.json()["farm_id"] == str(farm.id)
    outsider = create_user(db_session, email="settings-outsider@example.com")
    assert client.get(f"/api/v1/farms/{farm.id}/settings", headers=authorization_header(outsider)).status_code in {403, 404}


def test_backup_endpoints_enforce_system_admin_without_farm_bypass(client, db_session):
    owner = create_user(db_session, email="backup-owner@example.com"); create_owned_farm(db_session, owner=owner)
    assert client.get("/api/v1/admin/backups/dashboard", headers=authorization_header(owner)).status_code == 403
    admin = create_user(db_session, email="backup-admin@example.com"); admin.is_system_admin = True; db_session.commit()
    dashboard = client.get("/api/v1/admin/backups/dashboard", headers=authorization_header(admin))
    assert dashboard.status_code == 200 and dashboard.json()["scheduler_running"] is False
    queued = client.post("/api/v1/admin/backups/jobs", headers=authorization_header(admin), json={"request_id": "8ef70240-161e-44b9-8cdc-b2043fc44331", "backup_type": "ON_DEMAND", "current_password": "ValidPassword123!"})
    assert queued.status_code == 202 and queued.json()["status"] == "PENDING"
    assert db_session.scalars(select(SecurityEvent).where(SecurityEvent.user_id == owner.id)).all() == []
