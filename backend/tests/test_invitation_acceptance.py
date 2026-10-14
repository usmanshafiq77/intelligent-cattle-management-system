import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models.farm import Farm
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User, UserStatus
from app.services import invitations as invitation_service
from tests.helpers import (
    authorization_header,
    create_invitation,
    create_owned_farm,
    create_user,
)


pytestmark = pytest.mark.integration


def _accept(client, user, raw_token):
    return client.post(
        "/api/v1/invitations/accept",
        json={"token": raw_token},
        headers=authorization_header(user),
    )


@pytest.mark.parametrize(
    "role",
    [
        FarmRole.WORKER,
        FarmRole.FARM_MANAGER,
        FarmRole.VETERINARIAN,
    ],
)
def test_accepts_supported_roles_atomically(
    client,
    db_session,
    role,
):
    owner = create_user(
        db_session,
        email=f"owner-{role.value.lower()}@example.com",
    )
    invitee = create_user(
        db_session,
        email=f"invitee-{role.value.lower()}@example.com",
    )
    farm = create_owned_farm(
        db_session,
        owner=owner,
        name=f"{role.value} Farm",
    )
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
        role=role,
    )

    response = _accept(client, invitee, raw_token)

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "farm_id",
        "farm_name",
        "membership_id",
        "role",
        "membership_status",
        "accepted_at",
    }
    assert payload["farm_id"] == str(farm.id)
    assert payload["farm_name"] == farm.name
    assert payload["role"] == role.value
    assert payload["membership_status"] == MemberStatus.ACTIVE.value

    membership = db_session.scalar(
        select(FarmMember).where(
            FarmMember.farm_id == farm.id,
            FarmMember.user_id == invitee.id,
        )
    )
    db_session.refresh(invitation)
    assert membership is not None
    assert membership.role == role
    assert membership.status == MemberStatus.ACTIVE
    assert invitation.status == InvitationStatus.ACCEPTED
    assert invitation.accepted_at is not None


def test_wrong_email_is_rejected_without_state_change(client, db_session):
    owner = create_user(db_session, email="wrong-owner@example.com")
    invitee = create_user(db_session, email="intended@example.com")
    wrong_user = create_user(db_session, email="wrong@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )

    response = _accept(client, wrong_user, raw_token)

    assert response.status_code == 400
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.PENDING
    assert db_session.scalar(
        select(func.count(FarmMember.id)).where(
            FarmMember.farm_id == farm.id,
            FarmMember.user_id == wrong_user.id,
        )
    ) == 0


def test_unverified_email_is_rejected(client, db_session):
    owner = create_user(db_session, email="unverified-owner@example.com")
    invitee = create_user(
        db_session,
        email="unverified-invitee@example.com",
        verified=False,
    )
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )

    assert _accept(client, invitee, raw_token).status_code == 400
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.PENDING


def test_invalid_token_is_rejected(client, db_session):
    user = create_user(db_session, email="invalid-token@example.com")
    response = _accept(client, user, "x" * 32)
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invitation is invalid or cannot be accepted"
    }


def test_expired_token_is_rejected(client, db_session):
    owner = create_user(db_session, email="expired-owner@example.com")
    invitee = create_user(db_session, email="expired-user@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    assert _accept(client, invitee, raw_token).status_code == 400
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.PENDING


@pytest.mark.parametrize(
    "unusable_status",
    [InvitationStatus.REVOKED, InvitationStatus.ACCEPTED],
)
def test_revoked_and_already_accepted_invitations_are_rejected(
    client,
    db_session,
    unusable_status,
):
    suffix = unusable_status.value.lower()
    owner = create_user(
        db_session,
        email=f"{suffix}-owner@example.com",
    )
    invitee = create_user(
        db_session,
        email=f"{suffix}-invitee@example.com",
    )
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, _ = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
        status=unusable_status,
    )

    assert _accept(client, invitee, raw_token).status_code == 400


def test_accepted_token_cannot_be_replayed(client, db_session):
    owner = create_user(db_session, email="replay-owner@example.com")
    invitee = create_user(db_session, email="replay-user@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, _ = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )

    assert _accept(client, invitee, raw_token).status_code == 200
    assert _accept(client, invitee, raw_token).status_code == 400
    assert db_session.scalar(
        select(func.count(FarmMember.id)).where(
            FarmMember.farm_id == farm.id,
            FarmMember.user_id == invitee.id,
        )
    ) == 1


@pytest.mark.parametrize(
    "membership_status",
    [MemberStatus.ACTIVE, MemberStatus.PENDING, MemberStatus.INACTIVE],
)
def test_existing_membership_is_never_duplicated_or_reactivated(
    client,
    db_session,
    membership_status,
):
    suffix = membership_status.value.lower()
    owner = create_user(
        db_session,
        email=f"membership-owner-{suffix}@example.com",
    )
    invitee = create_user(
        db_session,
        email=f"membership-user-{suffix}@example.com",
    )
    farm = create_owned_farm(db_session, owner=owner)
    membership = FarmMember(
        farm_id=farm.id,
        user_id=invitee.id,
        role=FarmRole.WORKER,
        status=membership_status,
    )
    db_session.add(membership)
    db_session.commit()
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
        role=FarmRole.FARM_MANAGER,
    )

    response = _accept(client, invitee, raw_token)

    assert response.status_code == 409
    db_session.refresh(membership)
    db_session.refresh(invitation)
    assert membership.status == membership_status
    assert membership.role == FarmRole.WORKER
    assert invitation.status == InvitationStatus.PENDING


def test_inactive_user_cannot_accept(client, db_session):
    owner = create_user(db_session, email="inactive-accept-owner@example.com")
    invitee = create_user(
        db_session,
        email="inactive-accept-user@example.com",
        status=UserStatus.INACTIVE,
    )
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )

    assert _accept(client, invitee, raw_token).status_code == 403
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.PENDING


def test_accepted_membership_does_not_grant_cross_farm_access(
    client,
    db_session,
):
    first_owner = create_user(db_session, email="isolation-owner-a@example.com")
    second_owner = create_user(db_session, email="isolation-owner-b@example.com")
    invitee = create_user(db_session, email="isolation-user@example.com")
    first_farm = create_owned_farm(
        db_session,
        owner=first_owner,
        name="Allowed Farm",
    )
    second_farm = create_owned_farm(
        db_session,
        owner=second_owner,
        name="Other Farm",
    )
    raw_token, _ = create_invitation(
        db_session,
        farm=first_farm,
        invited_by=first_owner,
        email=invitee.email,
    )

    assert _accept(client, invitee, raw_token).status_code == 200
    assert client.get(
        f"/api/v1/farms/{second_farm.id}",
        headers=authorization_header(invitee),
    ).status_code == 404


def test_owner_role_is_defensively_rejected(
    client,
    db_session,
    monkeypatch,
):
    owner = create_user(db_session, email="elevation-owner@example.com")
    invitee = create_user(db_session, email="elevation-user@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )
    original_guard = invitation_service.get_redeemable_invitation

    def forged_owner_invitation(*args, **kwargs):
        result = original_guard(*args, **kwargs)
        result.role = FarmRole.FARM_OWNER
        return result

    monkeypatch.setattr(
        invitation_service,
        "get_redeemable_invitation",
        forged_owner_invitation,
    )

    assert _accept(client, invitee, raw_token).status_code == 400
    db_session.refresh(invitation)
    assert invitation.role == FarmRole.WORKER
    assert invitation.status == InvitationStatus.PENDING


def test_current_owner_policy_mismatch_rejects_acceptance(
    client,
    db_session,
):
    current_owner = create_user(
        db_session,
        email="current-owner@example.com",
    )
    former_owner = create_user(
        db_session,
        email="former-owner@example.com",
    )
    invitee = create_user(
        db_session,
        email="ownership-invitee@example.com",
    )
    farm = create_owned_farm(db_session, owner=current_owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=former_owner,
        email=invitee.email,
    )

    assert _accept(client, invitee, raw_token).status_code == 400
    db_session.refresh(invitation)
    assert invitation.status == InvitationStatus.PENDING


def test_acceptance_reuses_existing_redeemable_guard(
    client,
    db_session,
    monkeypatch,
):
    owner = create_user(db_session, email="guard-reuse-owner@example.com")
    invitee = create_user(db_session, email="guard-reuse-user@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, _ = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )
    original_guard = invitation_service.get_redeemable_invitation
    calls = 0

    def tracking_guard(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original_guard(*args, **kwargs)

    monkeypatch.setattr(
        invitation_service,
        "get_redeemable_invitation",
        tracking_guard,
    )

    assert _accept(client, invitee, raw_token).status_code == 200
    assert calls == 1


def test_acceptance_rolls_back_membership_and_invitation_together(
    client,
    db_session,
    monkeypatch,
):
    owner = create_user(db_session, email="rollback-accept-owner@example.com")
    invitee = create_user(db_session, email="rollback-accept-user@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    raw_token, invitation = create_invitation(
        db_session,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )

    def fail_commit():
        db_session.flush()
        raise SQLAlchemyError("forced acceptance commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    response = _accept(client, invitee, raw_token)

    assert response.status_code == 500
    db_session.expire_all()
    restored_invitation = db_session.get(Invitation, invitation.id)
    assert restored_invitation.status == InvitationStatus.PENDING
    assert restored_invitation.accepted_at is None
    assert db_session.scalar(
        select(func.count(FarmMember.id)).where(
            FarmMember.farm_id == farm.id,
            FarmMember.user_id == invitee.id,
        )
    ) == 0


def test_concurrent_acceptance_allows_exactly_one_success(pg_engine):
    unique = uuid.uuid4().hex
    setup = Session(pg_engine, expire_on_commit=False)
    owner = create_user(setup, email=f"accept-owner-{unique}@example.com")
    invitee = create_user(
        setup,
        email=f"accept-invitee-{unique}@example.com",
    )
    farm = create_owned_farm(
        setup,
        owner=owner,
        name=f"Acceptance Farm {unique}",
    )
    raw_token, invitation = create_invitation(
        setup,
        farm=farm,
        invited_by=owner,
        email=invitee.email,
    )
    owner_id = owner.id
    invitee_id = invitee.id
    farm_id = farm.id
    invitation_id = invitation.id
    headers = authorization_header(invitee)
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

    def attempt_acceptance(_number: int) -> int:
        barrier.wait()
        response = test_client.post(
            "/api/v1/invitations/accept",
            json={"token": raw_token},
            headers=headers,
        )
        return response.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt_acceptance, (1, 2)))
    finally:
        test_client.close()
        app.dependency_overrides.clear()

    assert sorted(results) == [200, 400]

    cleanup = Session(pg_engine)
    assert cleanup.scalar(
        select(func.count(FarmMember.id)).where(
            FarmMember.farm_id == farm_id,
            FarmMember.user_id == invitee_id,
        )
    ) == 1
    accepted = cleanup.get(Invitation, invitation_id)
    assert accepted.status == InvitationStatus.ACCEPTED
    assert accepted.accepted_at is not None
    cleanup.execute(delete(Farm).where(Farm.id == farm_id))
    cleanup.execute(
        delete(User).where(User.id.in_([owner_id, invitee_id]))
    )
    cleanup.commit()
    cleanup.close()


def test_creation_hides_token_outside_local_environments(
    client,
    db_session,
    memory_email_sender,
    monkeypatch,
):
    owner = create_user(db_session, email="production-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    monkeypatch.setattr(get_settings(), "APP_ENV", "production")

    response = client.post(
        f"/api/v1/farms/{farm.id}/invitations",
        json={"email": "production-invitee@example.com", "role": "WORKER"},
        headers=authorization_header(owner),
    )

    assert response.status_code == 201
    assert "invitation_token" not in response.json()
    assert len(memory_email_sender.invitation_messages) == 1
