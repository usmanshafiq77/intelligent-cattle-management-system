import pytest

from app.core.config import get_settings
from app.models.cattle import CattleMedia
from app.services.media_storage import LocalMediaStorage, get_media_storage
from tests.helpers import authorization_header, create_owned_farm, create_user
from tests.test_cattle import register


pytestmark = pytest.mark.integration

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"safe-test-image-content"


def upload(client, farm, owner, cattle_id, **kwargs):
    filename = kwargs.get("filename", "profile.png")
    purpose = kwargs.get("purpose", "PROFILE")
    content = kwargs.get("content", PNG_BYTES)
    content_type = kwargs.get("content_type", "image/png")
    return client.post(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/media",
        params={"filename": filename, "purpose": purpose},
        headers={**authorization_header(owner), "Content-Type": content_type},
        content=content,
    )


def test_media_upload_list_detail_content_and_soft_removal(client, db_session):
    owner = create_user(db_session, email="media-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    created = upload(client, farm, owner, cattle_id, purpose="IDENTIFICATION")
    assert created.status_code == 201
    media = created.json()
    assert media["content_type"] == "image/png"
    assert media["purpose"] == "IDENTIFICATION"
    assert "storage_key" not in media

    base = f"/api/v1/farms/{farm.id}/cattle/{cattle_id}/media"
    listed = client.get(base, headers=authorization_header(owner))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [media["id"]]
    detail = client.get(
        f"{base}/{media['id']}", headers=authorization_header(owner)
    )
    assert detail.status_code == 200
    content = client.get(
        f"{base}/{media['id']}/content",
        headers=authorization_header(owner),
    )
    assert content.status_code == 200
    assert content.content == PNG_BYTES

    profile = client.get(
        f"/api/v1/farms/{farm.id}/cattle/{cattle_id}",
        headers=authorization_header(owner),
    )
    assert profile.json()["media_count"] == 1
    removed = client.delete(
        f"{base}/{media['id']}", headers=authorization_header(owner)
    )
    assert removed.status_code == 204
    assert client.get(
        f"{base}/{media['id']}", headers=authorization_header(owner)
    ).status_code == 404
    stored = db_session.get(CattleMedia, media["id"])
    assert stored.removed_at is not None
    assert stored.removed_by_id == owner.id


@pytest.mark.parametrize(
    "filename,content,content_type",
    [
        ("../escape.png", PNG_BYTES, "image/png"),
        ("fake.png", b"not-an-image", "image/png"),
        ("mismatch.jpg", PNG_BYTES, "image/jpeg"),
    ],
)
def test_media_rejects_unsafe_filename_or_content(
    client, db_session, filename, content, content_type
):
    owner = create_user(
        db_session, email=f"media-invalid-{abs(hash(filename))}@example.com"
    )
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    response = upload(
        client,
        farm,
        owner,
        cattle_id,
        filename=filename,
        content=content,
        content_type=content_type,
    )
    assert response.status_code == 422


def test_media_size_limit_is_enforced(client, db_session, monkeypatch):
    owner = create_user(db_session, email="media-size-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]
    monkeypatch.setattr(get_settings(), "CATTLE_MEDIA_MAX_BYTES", 8)
    response = upload(client, farm, owner, cattle_id)
    assert response.status_code == 413


def test_media_is_not_accessible_across_farms(client, db_session):
    owner_a = create_user(db_session, email="media-scope-a@example.com")
    owner_b = create_user(db_session, email="media-scope-b@example.com")
    farm_a = create_owned_farm(db_session, owner=owner_a, name="Media A")
    farm_b = create_owned_farm(db_session, owner=owner_b, name="Media B")
    cattle_b = register(client, farm_b, owner_b).json()["id"]
    media = upload(client, farm_b, owner_b, cattle_b).json()
    response = client.get(
        f"/api/v1/farms/{farm_a.id}/cattle/{cattle_b}/media/{media['id']}",
        headers=authorization_header(owner_a),
    )
    assert response.status_code == 404


def test_media_file_is_removed_when_database_commit_fails(
    client, db_session, monkeypatch
):
    owner = create_user(db_session, email="media-rollback-owner@example.com")
    farm = create_owned_farm(db_session, owner=owner)
    cattle_id = register(client, farm, owner).json()["id"]

    class TrackingStorage:
        def __init__(self):
            self.files = {}

        def save(self, key, content):
            self.files[key] = content

        def delete(self, key):
            self.files.pop(key, None)

        def resolve(self, key):
            raise FileNotFoundError(key)

    storage = TrackingStorage()
    client.app.dependency_overrides[get_media_storage] = lambda: storage

    def fail_commit():
        raise RuntimeError("simulated database failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    response = upload(client, farm, owner, cattle_id)
    assert response.status_code == 500
    assert storage.files == {}


def test_local_storage_rejects_traversal_keys(tmp_path):
    storage = LocalMediaStorage(tmp_path / "root")
    with pytest.raises(ValueError):
        storage.save("../escape.png", PNG_BYTES)
    assert not (tmp_path / "escape.png").exists()
