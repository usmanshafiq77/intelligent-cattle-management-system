import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from app.main import app


def test_configured_web_origin_receives_restricted_cors_headers():
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:8081",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:8081"
    )
    assert "authorization" in response.headers[
        "access-control-allow-headers"
    ].lower()
    assert response.headers.get("access-control-allow-credentials") is None


def test_unknown_web_origin_is_not_granted_cors_access():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/health",
            headers={"Origin": "https://untrusted.example"},
        )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    ("app_environment", "origins"),
    [
        ("development", ["*"]),
        ("production", ["http://app.example.com"]),
    ],
)
def test_insecure_cors_configuration_is_rejected(
    app_environment, origins
):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV=app_environment,
            DB_PASSWORD="test-placeholder",
            JWT_SECRET_KEY="test-placeholder",
            CORS_ALLOWED_ORIGINS=origins,
        )
