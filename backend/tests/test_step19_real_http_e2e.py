import socket
import threading
import time
import uuid

import httpx
import pytest
import uvicorn
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.main import app
from app.services.email_delivery import get_email_sender
from app.services.media_storage import LocalMediaStorage, get_media_storage


pytestmark = pytest.mark.integration


def _available_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _expect(response: httpx.Response, status_code: int) -> dict:
    assert response.status_code == status_code, response.text
    return response.json() if response.content else {}


def test_complete_step19_workflow_over_real_http(
    pg_engine,
    memory_email_sender,
    tmp_path,
):
    """Exercise the frontend's core contracts through a real TCP/HTTP server.

    The session-scoped ``pg_engine`` is already pinned to a uniquely named
    disposable schema in the explicitly validated ``icms_test`` database.
    The fixture drops only that schema after the test session.
    """

    def override_db():
        session = Session(pg_engine, expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_email_sender] = lambda: memory_email_sender
    app.dependency_overrides[get_media_storage] = lambda: LocalMediaStorage(
        tmp_path / "media"
    )

    port = _available_port()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            lifespan="off",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "The isolated HTTP server did not start"

    unique = uuid.uuid4().hex
    owner_email = f"step19-owner-{unique}@example.com"
    member_email = f"step19-member-{unique}@example.com"
    password = "Step19-Test-Only-Password!42"

    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10) as client:
            assert _expect(client.get("/api/v1/health"), 200)["status"] == "ok"

            owner = _expect(
                client.post(
                    "/api/v1/auth/register",
                    json={
                        "full_name": "Step 19 Owner",
                        "email": owner_email,
                        "password": password,
                    },
                ),
                201,
            )
            assert owner["is_email_verified"] is False
            assert _expect(
                client.post(
                    "/api/v1/auth/verify-email",
                    json={"token": memory_email_sender.messages[-1].token},
                ),
                200,
            )["detail"] == "Email verified successfully"
            assert client.post(
                "/api/v1/auth/verify-email",
                    json={"token": "x" * 32},
            ).status_code == 400

            owner_token = _expect(
                client.post(
                    "/api/v1/auth/login",
                    json={"email": owner_email, "password": password},
                ),
                200,
            )["access_token"]
            owner_headers = {"Authorization": f"Bearer {owner_token}"}
            assert _expect(client.get("/api/v1/auth/me", headers=owner_headers), 200)[
                "id"
            ] == owner["id"]
            assert client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer expired-or-invalid"},
            ).status_code == 401

            farm = _expect(
                client.post(
                    "/api/v1/farms",
                    headers=owner_headers,
                    json={"name": f"Step 19 Farm {unique[:8]}"},
                ),
                201,
            )
            farm_id = farm["id"]
            owner_permissions = _expect(
                client.get(
                    f"/api/v1/farms/{farm_id}/staff/permissions/me",
                    headers=owner_headers,
                ),
                200,
            )
            assert owner_permissions["predefined_role"] == "FARM_OWNER"
            assert "staff.manage" in owner_permissions["permissions"]

            other_farm = _expect(
                client.post(
                    "/api/v1/farms",
                    headers=owner_headers,
                    json={"name": f"Isolated Farm {unique[:8]}"},
                ),
                201,
            )

            member = _expect(
                client.post(
                    "/api/v1/auth/register",
                    json={
                        "full_name": "Step 19 Member",
                        "email": member_email,
                        "password": password,
                    },
                ),
                201,
            )
            _expect(
                client.post(
                    "/api/v1/auth/verify-email",
                    json={"token": memory_email_sender.messages[-1].token},
                ),
                200,
            )
            member_token = _expect(
                client.post(
                    "/api/v1/auth/login",
                    json={"email": member_email, "password": password},
                ),
                200,
            )["access_token"]
            member_headers = {"Authorization": f"Bearer {member_token}"}

            invitation = _expect(
                client.post(
                    f"/api/v1/farms/{farm_id}/invitations",
                    headers=owner_headers,
                    json={"email": member_email, "role": "WORKER"},
                ),
                201,
            )
            assert "invitation_token" in invitation
            accepted = _expect(
                client.post(
                    "/api/v1/invitations/accept",
                    headers=member_headers,
                    json={"token": memory_email_sender.invitation_messages[-1].token},
                ),
                200,
            )
            membership_id = accepted["membership_id"]
            assert accepted["role"] == "WORKER"

            cattle_payload = {
                "tag_number": f"E2E-{unique[:10]}",
                "name": "Integration Daisy",
                "species": "CATTLE",
                "sex": "FEMALE",
                "category": "COW",
                "date_of_birth": "2023-01-15",
                "acquisition_method": "PURCHASED",
            }
            assert client.post(
                f"/api/v1/farms/{farm_id}/cattle",
                headers=member_headers,
                json=cattle_payload,
            ).status_code == 403
            assert client.get(
                f"/api/v1/farms/{other_farm['id']}", headers=member_headers
            ).status_code == 404

            changed = _expect(
                client.patch(
                    f"/api/v1/farms/{farm_id}/staff/{membership_id}/role",
                    headers=owner_headers,
                    json={"role": "FARM_MANAGER"},
                ),
                200,
            )
            assert changed["role"] == "FARM_MANAGER"
            assert "cattle.create" in _expect(
                client.get(
                    f"/api/v1/farms/{farm_id}/staff/permissions/me",
                    headers=member_headers,
                ),
                200,
            )["permissions"]

            cattle = _expect(
                client.post(
                    f"/api/v1/farms/{farm_id}/cattle",
                    headers=member_headers,
                    json=cattle_payload,
                ),
                201,
            )
            cattle_id = cattle["id"]
            assert _expect(
                client.get(
                    f"/api/v1/farms/{farm_id}/cattle/{cattle_id}",
                    headers=member_headers,
                ),
                200,
            )["tag_number"] == cattle_payload["tag_number"]
            assert _expect(
                client.patch(
                    f"/api/v1/farms/{farm_id}/cattle/{cattle_id}",
                    headers=member_headers,
                    json={"name": "Updated Integration Daisy"},
                ),
                200,
            )["name"] == "Updated Integration Daisy"
            cattle_list = _expect(
                client.get(
                    f"/api/v1/farms/{farm_id}/cattle?limit=100&offset=0",
                    headers=member_headers,
                ),
                200,
            )
            assert [item["id"] for item in cattle_list] == [cattle_id]

            _expect(
                client.patch(
                    f"/api/v1/farms/{farm_id}/staff/{membership_id}/status",
                    headers=owner_headers,
                    json={"status": "INACTIVE"},
                ),
                200,
            )
            assert client.get(
                f"/api/v1/farms/{farm_id}/cattle", headers=member_headers
            ).status_code == 404
            _expect(
                client.patch(
                    f"/api/v1/farms/{farm_id}/staff/{membership_id}/status",
                    headers=owner_headers,
                    json={"status": "ACTIVE"},
                ),
                200,
            )
            assert _expect(
                client.get(f"/api/v1/farms/{farm_id}", headers=member_headers),
                200,
            )["id"] == farm_id

            preflight = client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": "http://localhost:8081",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert preflight.status_code == 200
            assert preflight.headers["access-control-allow-origin"] == (
                "http://localhost:8081"
            )
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        app.dependency_overrides.clear()

    assert not thread.is_alive(), "The isolated HTTP server did not stop"
