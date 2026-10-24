import importlib

import pytest
from fastapi import HTTPException


main = importlib.import_module("app.main")


class FakeResult:
    def scalar_one(self):
        return 1


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        return FakeResult()


class FakeEngine:
    def connect(self):
        return FakeConnection()


def test_database_readiness_reports_expected_migration(monkeypatch):
    monkeypatch.setattr(main, "engine", FakeEngine())
    monkeypatch.setattr(
        main,
        "current_database_revision",
        lambda connection: main.EXPECTED_DATABASE_REVISION,
    )

    response = main.database_health_check()

    assert response == {
        "status": "ok",
        "database": "connected",
        "migration_revision": main.EXPECTED_DATABASE_REVISION,
    }


def test_database_readiness_rejects_schema_drift(monkeypatch):
    monkeypatch.setattr(main, "engine", FakeEngine())
    monkeypatch.setattr(
        main,
        "current_database_revision",
        lambda connection: "older-revision",
    )

    with pytest.raises(HTTPException) as error:
        main.database_health_check()

    assert error.value.status_code == 503
    assert error.value.detail == "Database migration required"
