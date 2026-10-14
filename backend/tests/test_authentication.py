from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.user import User, UserStatus
from app.services.email_verification import issue_verification_token
from tests.helpers import authorization_header, create_user


pytestmark = pytest.mark.integration


REGISTER_PAYLOAD = {
    "full_name": "New User",
    "email": "new.user@example.com",
    "password": "ValidPassword123!",
}


def test_successful_registration_and_duplicate(
    client,
    db_session,
    memory_email_sender,
):
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    assert response.json()["email"] == "new.user@example.com"
    assert response.json()["is_email_verified"] is False
    assert len(memory_email_sender.messages) == 1

    duplicate = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "email": "NEW.USER@example.com"},
    )
    assert duplicate.status_code == 409
    assert db_session.scalar(select(func.count(User.id))) == 1


def test_successful_login_and_invalid_credentials(client, db_session):
    create_user(
        db_session,
        email="login@example.com",
        password="ValidPassword123!",
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "LOGIN@example.com",
            "password": "ValidPassword123!",
        },
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "wrong"},
    )
    missing_account = client.post(
        "/api/v1/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
    )
    assert wrong_password.status_code == 401
    assert missing_account.status_code == 401
    assert wrong_password.json() == missing_account.json()


def test_missing_invalid_and_expired_jwt(client, db_session):
    user = create_user(db_session, email="jwt@example.com")

    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
    ).status_code == 401

    settings = get_settings()
    now = datetime.now(timezone.utc)
    expired_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
            "type": "access",
        },
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401


def test_inactive_account_cannot_login_or_use_token(client, db_session):
    user = create_user(
        db_session,
        email="inactive@example.com",
        status=UserStatus.INACTIVE,
    )

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": "ValidPassword123!",
        },
    )
    assert login.status_code == 403
    assert client.get(
        "/api/v1/auth/me",
        headers=authorization_header(user),
    ).status_code == 403


def test_email_verification_is_single_use(
    client,
    db_session,
    memory_email_sender,
):
    registered = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "email": "verify@example.com"},
    )
    assert registered.status_code == 201
    token = memory_email_sender.messages[-1].token

    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"token": token},
    )
    assert verified.status_code == 200

    user = db_session.scalar(
        select(User).where(User.email == "verify@example.com")
    )
    assert user.email_verified_at is not None

    replay = client.post(
        "/api/v1/auth/verify-email",
        json={"token": token},
    )
    assert replay.status_code == 400


def test_expired_email_verification_token_is_rejected(client, db_session):
    user = create_user(
        db_session,
        email="expired-verification@example.com",
        verified=False,
    )
    raw_token, _ = issue_verification_token(
        db_session,
        user=user,
        lifetime_minutes=1,
        now=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": raw_token},
    )
    assert response.status_code == 400
    db_session.refresh(user)
    assert user.email_verified_at is None


def test_resend_does_not_disclose_account_existence(
    client,
    db_session,
    memory_email_sender,
):
    create_user(
        db_session,
        email="resend@example.com",
        verified=False,
    )

    existing = client.post(
        "/api/v1/auth/verification/resend",
        json={"email": "resend@example.com"},
    )
    missing = client.post(
        "/api/v1/auth/verification/resend",
        json={"email": "missing@example.com"},
    )
    assert existing.status_code == 202
    assert missing.status_code == 202
    assert existing.json() == missing.json()
    assert len(memory_email_sender.messages) == 1


def test_login_and_registration_rate_limits_return_429(client):
    settings = get_settings()
    settings.AUTH_RATE_LIMIT_ENABLED = True
    settings.LOGIN_RATE_LIMIT_REQUESTS = 2
    settings.REGISTER_RATE_LIMIT_REQUESTS = 1
    settings.VERIFICATION_RESEND_RATE_LIMIT_REQUESTS = 1

    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "limited@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
    limited_login = client.post(
        "/api/v1/auth/login",
        json={"email": "limited@example.com", "password": "wrong"},
    )
    assert limited_login.status_code == 429
    assert "Retry-After" in limited_login.headers

    first_registration = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "email": "limited-register@example.com"},
    )
    assert first_registration.status_code == 201
    limited_registration = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "email": "limited-register@example.com"},
    )
    assert limited_registration.status_code == 429

    first_resend = client.post(
        "/api/v1/auth/verification/resend",
        json={"email": "resend-limited@example.com"},
    )
    limited_resend = client.post(
        "/api/v1/auth/verification/resend",
        json={"email": "resend-limited@example.com"},
    )
    assert first_resend.status_code == 202
    assert limited_resend.status_code == 429
