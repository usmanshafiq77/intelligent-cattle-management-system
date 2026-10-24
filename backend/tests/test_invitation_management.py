from datetime import datetime, timedelta, timezone

import pytest

from app.models.farm_member import FarmRole
from app.models.invitation import InvitationStatus
from tests.helpers import (
    authorization_header,
    create_invitation,
    create_owned_farm,
    create_user,
)


pytestmark = pytest.mark.integration


def test_owner_can_list_and_view_safe_invitation_metadata(client, db_session):
    owner = create_user(db_session, email="invite-list-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    _, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email="invite-list-target@example.com",
    )
    listed = client.get(
        f"/api/v1/farms/{farm.id}/invitations",
        headers=authorization_header(owner),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "token_hash" not in listed.json()[0]
    assert "invitation_token" not in listed.json()[0]
    viewed = client.get(
        f"/api/v1/farms/{farm.id}/invitations/{invitation.id}",
        headers=authorization_header(owner),
    )
    assert viewed.status_code == 200
    assert viewed.json()["email"] == "invite-list-target@example.com"
    assert "token_hash" not in viewed.json()


def test_non_owner_cannot_administer_invitations(client, db_session):
    owner = create_user(db_session, email="invite-admin-owner@example.com")
    manager = create_user(db_session, email="invite-admin-manager@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    from tests.test_staff import add_staff

    add_staff(db_session, farm, manager, FarmRole.FARM_MANAGER)
    response = client.get(
        f"/api/v1/farms/{farm.id}/invitations",
        headers=authorization_header(manager),
    )
    assert response.status_code == 403


def test_revoke_prevents_acceptance_and_cannot_be_replayed(client, db_session):
    owner = create_user(db_session, email="revoke-owner@example.com")
    invitee = create_user(db_session, email="revoke-target@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )
    revoked = client.post(
        f"/api/v1/farms/{farm.id}/invitations/{invitation.id}/revoke",
        headers=authorization_header(owner),
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOKED"
    replay = client.post(
        f"/api/v1/farms/{farm.id}/invitations/{invitation.id}/revoke",
        headers=authorization_header(owner),
    )
    assert replay.status_code == 409
    acceptance = client.post(
        "/api/v1/invitations/accept",
        headers=authorization_header(invitee),
        json={"token": raw_token},
    )
    assert acceptance.status_code == 400


def test_reissue_rotates_token_and_revokes_original(
    client, db_session, memory_email_sender
):
    owner = create_user(db_session, email="reissue-owner@example.com")
    invitee = create_user(db_session, email="reissue-target@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    old_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )
    response = client.post(
        f"/api/v1/farms/{farm.id}/invitations/{invitation.id}/reissue",
        headers=authorization_header(owner),
    )
    assert response.status_code == 201
    replacement = response.json()
    assert replacement["id"] != str(invitation.id)
    assert replacement["invitation_token"] != old_token
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.REVOKED
    assert len(memory_email_sender.invitation_messages) == 1

    old_acceptance = client.post(
        "/api/v1/invitations/accept",
        headers=authorization_header(invitee),
        json={"token": old_token},
    )
    assert old_acceptance.status_code == 400
    new_acceptance = client.post(
        "/api/v1/invitations/accept",
        headers=authorization_header(invitee),
        json={"token": replacement["invitation_token"]},
    )
    assert new_acceptance.status_code == 200


def test_listing_reports_effective_expiry_without_mutating_invitation(
    client,
    db_session,
):
    owner = create_user(db_session, email="expiry-list-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    _, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email="expiry-list-target@example.com",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    response = client.get(
        f"/api/v1/farms/{farm.id}/invitations?status=EXPIRED",
        headers=authorization_header(owner),
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(invitation.id)]
    assert response.json()[0]["status"] == "EXPIRED"
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.PENDING

    viewed = client.get(
        f"/api/v1/farms/{farm.id}/invitations/{invitation.id}",
        headers=authorization_header(owner),
    )
    assert viewed.status_code == 200
    assert viewed.json()["status"] == "EXPIRED"
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.PENDING


def test_invitation_create_reports_delivery_failure_without_losing_record(
    client,
    db_session,
    memory_email_sender,
    monkeypatch,
):
    owner = create_user(db_session, email="delivery-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)

    def fail_delivery(**kwargs):
        raise RuntimeError("simulated delivery outage")

    monkeypatch.setattr(
        memory_email_sender,
        "send_invitation_email",
        fail_delivery,
    )
    response = client.post(
        f"/api/v1/farms/{farm.id}/invitations",
        headers=authorization_header(owner),
        json={"email": "delivery-target@example.com", "role": "WORKER"},
    )

    assert response.status_code == 201
    assert response.json()["delivery_status"] == "FAILED"
    assert response.json()["status"] == "PENDING"


def test_expired_invitation_cannot_be_revoked_as_pending(client, db_session):
    owner = create_user(db_session, email="expiry-revoke-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    _, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email="expiry-revoke-target@example.com",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    response = client.post(
        f"/api/v1/farms/{farm.id}/invitations/{invitation.id}/revoke",
        headers=authorization_header(owner),
    )
    assert response.status_code == 409
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.EXPIRED


def test_invitation_details_are_farm_scoped(client, db_session):
    owner_a = create_user(db_session, email="invite-scope-a@example.com")
    owner_b = create_user(db_session, email="invite-scope-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="Invite A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Invite B")
    _, invitation_b = create_invitation(
        db_session,
        farm=farm_b,
        invited_by=owner_b,
        email="invite-scope-target@example.com",
    )
    response = client.get(
        f"/api/v1/farms/{farm_a.id}/invitations/{invitation_b.id}",
        headers=authorization_header(owner_a),
    )
    assert response.status_code == 404
