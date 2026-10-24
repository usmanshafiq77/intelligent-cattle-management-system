import uuid

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.v1.auth import get_current_user, router
from app.models.user import User, UserStatus
from app.services.media_storage import LocalMediaStorage, get_media_storage


PNG = b"\x89PNG\r\n\x1a\n" + b"profile-image"


def user(user_id: uuid.UUID) -> User:
    return User(
        id=user_id,
        full_name="Avatar User",
        email=f"{user_id}@example.com",
        password_hash="unused",
        status=UserStatus.ACTIVE,
    )


def avatar_client(tmp_path, identity):
    application = FastAPI()
    application.include_router(router, prefix="/api/v1")
    application.dependency_overrides[get_current_user] = identity
    application.dependency_overrides[get_media_storage] = lambda: LocalMediaStorage(tmp_path / "media")
    return TestClient(application)


def test_avatar_upload_rejects_unauthenticated_user(tmp_path):
    def unauthorized():
        raise HTTPException(status_code=401, detail="Authentication required")

    client = avatar_client(tmp_path, unauthorized)
    response = client.put("/api/v1/auth/me/avatar", content=PNG, headers={"Content-Type": "image/png"})
    assert response.status_code == 401


def test_avatar_upload_validates_content_and_declared_type(tmp_path):
    current = user(uuid.uuid4())
    client = avatar_client(tmp_path, lambda: current)
    invalid = client.put("/api/v1/auth/me/avatar", content=b"not-an-image", headers={"Content-Type": "image/png"})
    mismatch = client.put("/api/v1/auth/me/avatar", content=PNG, headers={"Content-Type": "image/jpeg"})
    assert invalid.status_code == 422
    assert mismatch.status_code == 422


def test_avatar_upload_enforces_configured_size_limit(tmp_path, monkeypatch):
    current = user(uuid.uuid4())
    client = avatar_client(tmp_path, lambda: current)
    monkeypatch.setattr(
        "app.api.v1.auth.get_settings",
        lambda: type("Settings", (), {"PROFILE_AVATAR_MAX_BYTES": 8})(),
    )
    response = client.put("/api/v1/auth/me/avatar", content=PNG, headers={"Content-Type": "image/png"})
    assert response.status_code == 413


def test_avatar_is_owned_replaced_and_removed_by_authenticated_user(tmp_path):
    first = user(uuid.uuid4())
    second = user(uuid.uuid4())
    identity = {"current": first}
    client = avatar_client(tmp_path, lambda: identity["current"])

    assert client.get("/api/v1/auth/me/avatar").status_code == 404
    assert client.put("/api/v1/auth/me/avatar", content=PNG, headers={"Content-Type": "image/png"}).status_code == 204
    assert client.get("/api/v1/auth/me/avatar").content == PNG

    replacement = PNG + b"-replacement"
    assert client.put("/api/v1/auth/me/avatar", content=replacement, headers={"Content-Type": "image/png"}).status_code == 204
    assert client.get("/api/v1/auth/me/avatar").content == replacement

    identity["current"] = second
    assert client.get("/api/v1/auth/me/avatar").status_code == 404
    identity["current"] = first
    assert client.delete("/api/v1/auth/me/avatar").status_code == 204
    assert client.get("/api/v1/auth/me/avatar").status_code == 404
    assert client.delete("/api/v1/auth/me/avatar").status_code == 204
