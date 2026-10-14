import hashlib
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.models.farm import Farm
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User
from app.services.invitations import (
    InvitationAcceptanceError,
    get_redeemable_invitation,
)
from tests.helpers import (
    authorization_header,
    create_owned_farm,
    create_user,
)


pytestmark = pytest.mark.integration


def _invite(client, owner, farm, email, role="WORKER"):
    return client.post(
        f"/api/v1/farms/{farm.id}/invitations",
        json={"email": email, "role": role},
        headers=authorization_header(owner),
    )


def test_only_authoritative_owner_can_invite(client, db_session):
    owner = create_user(db_session, email="invite-owner@example.com")
    worker = create_user(db_session, email="invite-worker@example.com")
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

    response = _invite(client, worker, farm, "staff@example.com")
    assert response.status_code == 403


def test_invalid_role_and_owner_elevation_are_rejected(client, db_session):
    owner = create_user(db_session, email="role-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)

    assert _invite(
        client,
        owner,
        farm,
        "staff@example.com",
        role="INVALID_ROLE",
    ).status_code == 422
    assert _invite(
        client,
        owner,
        farm,
        "staff@example.com",
        role="FARM_OWNER",
    ).status_code == 422

    db_session.add(
        Invitation(
            farm_id=farm.id,
            invited_by_id=owner.id,
            email="direct-owner@example.com",
            role=FarmRole.FARM_OWNER,
            token_hash="a" * 64,
            status=InvitationStatus.PENDING,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_duplicate_pending_invitation_returns_409_and_hashes_token(
    client,
    db_session,
):
    owner = create_user(db_session, email="duplicate-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)

    first = _invite(client, owner, farm, "Staff@Example.com")
    second = _invite(client, owner, farm, "staff@example.com")
    assert first.status_code == 201
    assert second.status_code == 409

    raw_token = first.json()["invitation_token"]
    invitation = db_session.scalar(
        select(Invitation).where(Invitation.farm_id == farm.id)
    )
    assert invitation.email == "staff@example.com"
    assert invitation.token_hash != raw_token
    assert invitation.token_hash == hashlib.sha256(
        raw_token.encode("utf-8")
    ).hexdigest()


def test_expired_pending_invitation_is_expired_before_replacement(
    client,
    db_session,
):
    owner = create_user(db_session, email="expiry-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    expired = Invitation(
        farm_id=farm.id,
        invited_by_id=owner.id,
        email="expired-staff@example.com",
        role=FarmRole.WORKER,
        token_hash="b" * 64,
        status=InvitationStatus.PENDING,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(expired)
    db_session.commit()

    response = _invite(
        client,
        owner,
        farm,
        "expired-staff@example.com",
    )
    assert response.status_code == 201
    db_session.refresh(expired)
    assert expired.status == InvitationStatus.EXPIRED


def test_inactive_or_non_owner_membership_cannot_invite(client, db_session):
    user = create_user(db_session, email="inactive-inviter@example.com")
    farm = Farm(name="No Active Owner", owner_id=user.id)
    db_session.add(farm)
    db_session.flush()
    db_session.add(
        FarmMember(
            farm_id=farm.id,
            user_id=user.id,
            role=FarmRole.FARM_MANAGER,
            status=MemberStatus.INACTIVE,
        )
    )
    db_session.commit()

    assert _invite(
        client,
        user,
        farm,
        "staff@example.com",
    ).status_code == 403


def test_invitation_acceptance_guard_requires_verified_matching_identity(
    db_session,
):
    owner = create_user(db_session, email="guard-owner@example.com")
    invitee = create_user(
        db_session,
        email="guard-invitee@example.com",
        verified=False,
    )
    farm = create_owned_farm(db_session, owner=owner)
    raw_token = "secure-test-invitation-token"
    invitation = Invitation(
        farm_id=farm.id,
        invited_by_id=owner.id,
        email=invitee.email,
        role=FarmRole.WORKER,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        status=InvitationStatus.PENDING,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(invitation)
    db_session.commit()

    with pytest.raises(InvitationAcceptanceError):
        get_redeemable_invitation(
            db_session,
            raw_token=raw_token,
            user=invitee,
        )

    invitee.email_verified_at = datetime.now(timezone.utc)
    db_session.commit()
    assert get_redeemable_invitation(
        db_session,
        raw_token=raw_token,
        user=invitee,
    ).id == invitation.id

    for unusable_status in (
        InvitationStatus.ACCEPTED,
        InvitationStatus.REVOKED,
        InvitationStatus.EXPIRED,
    ):
        invitation.status = unusable_status
        db_session.commit()
        with pytest.raises(InvitationAcceptanceError):
            get_redeemable_invitation(
                db_session,
                raw_token=raw_token,
                user=invitee,
            )


def test_concurrent_pending_invitations_allow_only_one(pg_engine):
    unique = uuid.uuid4().hex
    setup = Session(pg_engine, expire_on_commit=False)
    owner = create_user(setup, email=f"owner-{unique}@example.com")
    farm = create_owned_farm(setup, owner=owner, name=f"Farm {unique}")
    owner_id = owner.id
    farm_id = farm.id
    setup.close()

    email = f"concurrent-{unique}@example.com"
    barrier = threading.Barrier(2)

    def override_db():
        session = Session(pg_engine, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    test_client = TestClient(app)
    headers = authorization_header(owner)

    def attempt_request(_number: int) -> int:
        barrier.wait()
        response = test_client.post(
            f"/api/v1/farms/{farm_id}/invitations",
            json={"email": email, "role": "WORKER"},
            headers=headers,
        )
        return response.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt_request, (1, 2)))
    finally:
        test_client.close()
        app.dependency_overrides.clear()

    assert sorted(results) == [201, 409]

    cleanup = Session(pg_engine)
    assert cleanup.scalar(
        select(func.count(Invitation.id)).where(
            Invitation.farm_id == farm_id,
            Invitation.email == email,
            Invitation.status == InvitationStatus.PENDING,
        )
    ) == 1
    cleanup.execute(delete(Farm).where(Farm.id == farm_id))
    cleanup.execute(delete(User).where(User.id == owner_id))
    cleanup.commit()
    cleanup.close()
