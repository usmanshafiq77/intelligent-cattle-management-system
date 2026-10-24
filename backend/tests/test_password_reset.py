from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.models.password_reset import PasswordResetToken
from app.models.user import User, UserStatus
from app.services.password_reset import (
    InvalidPasswordResetTokenError,
    issue_password_reset_token,
    reset_password_with_token,
)
from tests.helpers import create_user


pytestmark = pytest.mark.integration

GENERIC_RESPONSE = {
    "detail": "If the account is eligible, password reset instructions will be sent."
}


def request_reset(client, email):
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


def test_forgot_password_is_generic_and_only_emails_eligible_account(
    client, db_session, memory_email_sender
):
    create_user(db_session, email="eligible@example.com")

    existing = request_reset(client, "  ELIGIBLE@example.com ")
    unknown = request_reset(client, "unknown@example.com")

    assert existing.status_code == unknown.status_code == 202
    assert existing.json() == unknown.json() == GENERIC_RESPONSE
    assert len(memory_email_sender.password_reset_messages) == 1
    assert memory_email_sender.password_reset_messages[0].recipient == "eligible@example.com"


@pytest.mark.parametrize(
    ("email", "status", "verified"),
    [
        ("pending@example.com", UserStatus.PENDING, False),
        ("inactive@example.com", UserStatus.INACTIVE, True),
        ("unverified@example.com", UserStatus.ACTIVE, False),
    ],
)
def test_forgot_password_does_not_issue_for_ineligible_accounts(
    client, db_session, memory_email_sender, email, status, verified
):
    create_user(db_session, email=email, status=status, verified=verified)
    response = request_reset(client, email)
    assert response.status_code == 202
    assert response.json() == GENERIC_RESPONSE
    assert memory_email_sender.password_reset_messages == []
    assert db_session.scalar(select(func.count(PasswordResetToken.id))) == 0


def test_valid_reset_is_one_time_changes_login_and_invalidates_existing_jwt(
    client, db_session, memory_email_sender
):
    user = create_user(db_session, email="reset@example.com", password="OldPassword123!")
    old_token = create_access_token(user.id, user.token_version)
    assert request_reset(client, user.email).status_code == 202
    raw_token = memory_email_sender.password_reset_messages[-1].token

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword123!"},
    )
    assert reset.status_code == 200
    db_session.refresh(user)
    assert user.token_version == 1
    assert verify_password("NewPassword123!", user.password_hash)

    assert client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "OldPassword123!"},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "NewPassword123!"},
    ).status_code == 200
    assert client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "AnotherPassword123!"},
    ).status_code == 400


def test_pre_migration_jwt_works_until_the_password_is_reset(
    client, db_session
):
    user = create_user(db_session, email="legacy-jwt@example.com")
    now = datetime.now(timezone.utc)
    settings = get_settings()
    legacy_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now,
            "exp": now + timedelta(minutes=10),
            "type": "access",
        },
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )
    headers = {"Authorization": f"Bearer {legacy_token}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    raw_token, _ = issue_password_reset_token(db_session, user=user)
    db_session.commit()
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword123!"},
    ).status_code == 200
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_invalid_expired_and_revoked_tokens_are_rejected(client, db_session):
    user = create_user(db_session, email="invalid-tokens@example.com")
    expired_raw, _ = issue_password_reset_token(
        db_session,
        user=user,
        lifetime_minutes=1,
        now=datetime.now(timezone.utc) - timedelta(minutes=2),
    )
    db_session.commit()
    fresh_raw, _ = issue_password_reset_token(db_session, user=user)
    db_session.commit()

    for token in ["x" * 43, expired_raw]:
        response = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "NewPassword123!"},
        )
        assert response.status_code == 400

    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": fresh_raw, "new_password": "NewPassword123!"},
    ).status_code == 200


def test_password_policy_is_enforced_before_token_consumption(client, db_session):
    user = create_user(db_session, email="policy@example.com")
    raw_token, token = issue_password_reset_token(db_session, user=user)
    db_session.commit()

    rejected = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "short"},
    )
    assert rejected.status_code == 422
    db_session.refresh(token)
    assert token.used_at is None


def test_hashing_failure_rolls_back_password_and_token(
    client, db_session, monkeypatch
):
    user = create_user(
        db_session,
        email="rollback@example.com",
        password="OldPassword123!",
    )
    raw_token, token = issue_password_reset_token(db_session, user=user)
    db_session.commit()

    def fail_hash(_password):
        raise RuntimeError("simulated hashing failure")

    monkeypatch.setattr(
        "app.services.password_reset.hash_password",
        fail_hash,
    )
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw_token, "new_password": "NewPassword123!"},
    )
    assert response.status_code == 500
    db_session.refresh(user)
    db_session.refresh(token)
    assert verify_password("OldPassword123!", user.password_hash)
    assert token.used_at is None


def test_issuing_a_new_token_revokes_the_previous_token(db_session):
    user = create_user(db_session, email="revoked@example.com")
    old_raw, old_token = issue_password_reset_token(db_session, user=user)
    db_session.commit()
    new_raw, _ = issue_password_reset_token(db_session, user=user)
    db_session.commit()
    db_session.refresh(old_token)
    assert old_token.revoked_at is not None
    with pytest.raises(InvalidPasswordResetTokenError):
        reset_password_with_token(
            db_session, raw_token=old_raw, new_password="NewPassword123!"
        )
    db_session.rollback()
    assert reset_password_with_token(
        db_session, raw_token=new_raw, new_password="NewPassword123!"
    ) == user


def test_password_reset_rate_limit_is_configurable(client):
    settings = get_settings()
    settings.AUTH_RATE_LIMIT_ENABLED = True
    settings.RESET_PASSWORD_RATE_LIMIT_REQUESTS = 1
    first = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "a" * 43, "new_password": "NewPassword123!"},
    )
    second = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "a" * 43, "new_password": "NewPassword123!"},
    )
    assert first.status_code == 400
    assert second.status_code == 429


def test_concurrent_token_consumption_has_exactly_one_winner(pg_engine):
    with Session(pg_engine) as setup:
        user = create_user(setup, email="concurrent-reset@example.com")
        user_id = user.id
        raw_token, _ = issue_password_reset_token(setup, user=user)
        setup.commit()

    def consume():
        with Session(pg_engine) as session:
            try:
                reset_password_with_token(
                    session, raw_token=raw_token, new_password="NewPassword123!"
                )
                session.commit()
                return "success"
            except InvalidPasswordResetTokenError:
                session.rollback()
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: consume(), range(2)))
    assert sorted(outcomes) == ["rejected", "success"]
    with Session(pg_engine) as cleanup:
        cleanup.execute(delete(User).where(User.id == user_id))
        cleanup.commit()


def test_concurrent_issuance_preserves_one_active_token(pg_engine):
    with Session(pg_engine) as setup:
        user = create_user(setup, email="concurrent-issue@example.com")
        user_id = user.id

    def issue():
        with Session(pg_engine) as session:
            user = session.get(User, user_id)
            try:
                issue_password_reset_token(session, user=user)
                session.commit()
                return "success"
            except IntegrityError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: issue(), range(2)))
    assert outcomes.count("success") >= 1
    with Session(pg_engine) as session:
        active = session.scalar(
            select(func.count(PasswordResetToken.id)).where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
            )
        )
        assert active == 1
    with Session(pg_engine) as cleanup:
        cleanup.execute(delete(User).where(User.id == user_id))
        cleanup.commit()
