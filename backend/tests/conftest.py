import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

# Safe defaults are installed before application modules construct Settings.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "icms_test")
os.environ.setdefault("DB_USER", "icms_test")
os.environ.setdefault("DB_PASSWORD", "test-only-placeholder")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-jwt-secret-that-is-not-used-outside-tests",
)
os.environ.setdefault("EMAIL_DELIVERY_MODE", "memory")
os.environ.setdefault("AUTH_RATE_LIMIT_ENABLED", "false")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.models  # noqa: F401, E402
from app.core.config import get_settings  # noqa: E402
from app.core.rate_limit import auth_rate_limiter  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.core.permissions import PERMISSION_CODES  # noqa: E402
from app.models.rbac import PermissionRecord  # noqa: E402
from app.services.email_delivery import get_email_sender  # noqa: E402


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


@dataclass
class SentVerification:
    recipient: str
    token: str
    expires_at: datetime


@dataclass
class SentInvitation:
    recipient: str
    token: str
    expires_at: datetime
    farm_name: str


class MemoryEmailSender:
    def __init__(self) -> None:
        self.messages: list[SentVerification] = []
        self.invitation_messages: list[SentInvitation] = []

    def send_verification_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
    ) -> None:
        self.messages.append(
            SentVerification(recipient, token, expires_at)
        )

    def send_invitation_email(
        self,
        *,
        recipient: str,
        token: str,
        expires_at: datetime,
        farm_name: str,
    ) -> None:
        self.invitation_messages.append(
            SentInvitation(recipient, token, expires_at, farm_name)
        )


def _validated_test_url():
    if not TEST_DATABASE_URL:
        return None

    url = make_url(TEST_DATABASE_URL)
    database = url.database or ""
    if not url.drivername.startswith("postgresql"):
        raise pytest.UsageError(
            "TEST_DATABASE_URL must use PostgreSQL; SQLite is forbidden."
        )
    if database == "icms_db":
        raise pytest.UsageError("Tests must never target icms_db.")
    if not (database.startswith("test_") or database.endswith("_test")):
        raise pytest.UsageError(
            "The test database name must start with test_ or end with _test."
        )
    return url


def pytest_collection_modifyitems(config, items):
    if TEST_DATABASE_URL:
        return
    marker = pytest.mark.skip(
        reason="TEST_DATABASE_URL is not configured for isolated PostgreSQL"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(marker)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    auth_rate_limiter.reset()
    yield
    auth_rate_limiter.reset()


@pytest.fixture(scope="session")
def pg_engine():
    url = _validated_test_url()
    if url is None:
        pytest.skip("No isolated PostgreSQL test database configured")

    admin_engine = create_engine(url, pool_pre_ping=True)
    schema_name = f"icms_test_{uuid.uuid4().hex}"

    with admin_engine.connect() as connection:
        actual_database = connection.scalar(text("SELECT current_database()"))
        if actual_database != url.database or actual_database == "icms_db":
            pytest.fail("Connected database failed the isolation check")
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        connection.commit()

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema_name}"},
    )

    try:
        Base.metadata.create_all(engine)
        with engine.begin() as connection:
            connected_database = connection.scalar(
                text("SELECT current_database()")
            )
            connected_schema = connection.scalar(
                text("SELECT current_schema()")
            )
            if connected_database != "icms_test":
                pytest.fail("Test engine is not connected to icms_test")
            if connected_schema != schema_name:
                pytest.fail("Test engine did not select its disposable schema")
            connection.execute(
                PermissionRecord.__table__.insert(),
                [{"code": code} for code in sorted(PERMISSION_CODES)],
            )
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as connection:
            connection.execute(
                text(f'DROP SCHEMA "{schema_name}" CASCADE')
            )
            connection.commit()
        admin_engine.dispose()


@pytest.fixture
def db_session(pg_engine):
    connection = pg_engine.connect()
    outer_transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if outer_transaction.is_active:
            outer_transaction.rollback()
        connection.close()


@pytest.fixture
def memory_email_sender():
    return MemoryEmailSender()


@pytest.fixture
def client(db_session, memory_email_sender):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_email_sender] = lambda: memory_email_sender
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()
