from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.normalization import normalize_email
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password_safely,
)
from app.schemas.invitation import InvitationCreate
from app.schemas.user import UserLogin, UserRegister
from app.services.email_verification import hash_verification_token
from app.services.invitations import generate_invitation_token


def test_email_normalization_is_consistent():
    assert normalize_email("  Person@Example.COM ") == "person@example.com"


def test_authentication_input_size_limits():
    with pytest.raises(ValidationError):
        UserRegister(
            full_name="Valid Name",
            email="user@example.com",
            password="x" * 129,
        )
    with pytest.raises(ValidationError):
        UserLogin(email="user@example.com", password="x" * 129)


def test_invitation_schema_forbids_owner_elevation():
    with pytest.raises(ValidationError):
        InvitationCreate(
            email="staff@example.com",
            role="FARM_OWNER",
        )


def test_password_verification_uses_real_and_dummy_hashes():
    encoded = hash_password("CorrectPassword123!")
    assert verify_password_safely("CorrectPassword123!", encoded)
    assert not verify_password_safely("wrong", encoded)
    assert not verify_password_safely("wrong", None)


def test_jwt_round_trip_invalid_and_expired_tokens():
    user_id = uuid4()
    payload = decode_access_token(create_access_token(user_id))
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-token")

    settings = get_settings()
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": str(user_id),
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
            "type": "access",
        },
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)


def test_security_tokens_are_random_and_only_hashes_are_persistable():
    first_raw, first_hash = generate_invitation_token()
    second_raw, second_hash = generate_invitation_token()

    assert first_raw != second_raw
    assert first_hash != second_hash
    assert len(first_hash) == 64
    assert hash_verification_token(first_raw) == first_hash
