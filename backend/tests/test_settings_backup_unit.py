import base64
import hashlib
import io
import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import uuid
import inspect

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.schemas.user import PasswordChange, UserPreferenceUpdate
from app.services.backup_crypto import BackupCryptoError, decrypt_file, encrypt_file, inspect_header
from app.services.backup_engine import BackupEngineError, create_database_backup, validate_restore_destination, verify_encrypted_backup
from app.services.backup_orchestrator import retention_candidates
from app.services.backup_orchestrator import process_next_backup
from app.services.google_drive import GoogleDriveAdapter, GoogleDriveError, GoogleDriveQuotaError, authorization_url
from app.services.secret_box import open_sealed, seal


def settings(tmp_path, key: bytes | None = None):
    return Settings(DB_PASSWORD=SecretStr("not-logged"), JWT_SECRET_KEY=SecretStr("unit-test-secret-with-more-than-32-characters"), DB_NAME="test_backup_unit", BACKUP_ROOT=tmp_path, BACKUP_ENCRYPTION_KEY=SecretStr(base64.urlsafe_b64encode(key or b"k" * 32).decode()))


def test_preferences_and_strong_password_validation():
    assert UserPreferenceUpdate(language="en", theme="midnight").theme == "midnight"
    with pytest.raises(ValidationError): UserPreferenceUpdate(language="ur")
    assert PasswordChange(current_password="old", new_password="Long!Password9").new_password
    with pytest.raises(ValidationError): PasswordChange(current_password="old", new_password="weakpassword")


def test_streaming_encryption_round_trip_and_corruption(tmp_path):
    source = tmp_path / "source.dump"; source.write_bytes((b"postgres-archive" * 10000) + b"end")
    encrypted = tmp_path / "backup.icmsbak"; restored = tmp_path / "restored.dump"; key = b"a" * 32
    metadata = encrypt_file(source, encrypted, key=key, key_id="primary")
    assert inspect_header(encrypted)["algorithm"] == "AES-256-GCM"
    assert verify_encrypted_backup(encrypted, expected_sha256=metadata["encrypted_sha256"])
    result = decrypt_file(encrypted, restored, keys={"primary": key})
    assert restored.read_bytes() == source.read_bytes()
    assert result["plaintext_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    damaged = bytearray(encrypted.read_bytes()); damaged[-20] ^= 1; corrupt = tmp_path / "corrupt.icmsbak"; corrupt.write_bytes(damaged)
    with pytest.raises(BackupCryptoError): decrypt_file(corrupt, tmp_path / "bad.dump", keys={"primary": key})
    with pytest.raises(BackupCryptoError): decrypt_file(encrypted, tmp_path / "wrong.dump", keys={"primary": b"b" * 32})


def test_oauth_token_envelope_is_authenticated():
    key = b"z" * 32; blob = seal("refresh-secret", key, context=b"context")
    assert b"refresh-secret" not in blob and open_sealed(blob, key, context=b"context") == "refresh-secret"
    with pytest.raises(Exception): open_sealed(blob, key, context=b"other")


def test_backup_engine_uses_custom_archive_and_cleans_plaintext(tmp_path):
    calls = []
    def runner(command, **kwargs):
        calls.append((command, kwargs))
        if "--file" in command: Path(command[command.index("--file") + 1]).write_bytes(b"valid-custom-dump")
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    result = create_database_backup(settings(tmp_path), now=datetime(2026, 1, 2, tzinfo=timezone.utc), runner=runner, metadata_loader=lambda *_: {"database": "test_backup_unit", "server_version_num": "180000", "table_count": 4, "critical_counts": {"users": 2}})
    assert result["path"].is_file() and result["path"].suffix == ".icmsbak"
    assert "--format" in calls[0][0] and "custom" in calls[0][0]
    assert "not-logged" not in " ".join(calls[0][0])
    assert calls[0][1]["env"]["PGPASSWORD"] == "not-logged"
    assert not list(tmp_path.glob("*.part"))


def test_failed_dump_leaves_no_partial_artifact(tmp_path):
    def runner(command, **kwargs): return SimpleNamespace(returncode=1, stdout="", stderr="sensitive database failure")
    with pytest.raises(BackupEngineError, match="did not produce"): create_database_backup(settings(tmp_path), runner=runner, metadata_loader=lambda *_: {})
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", ["icms_db", "icms_test", "production", "test_restore_"])
def test_restore_destination_refuses_protected_or_invalid_names(name):
    if name == "test_restore_": validate_restore_destination(name)
    else:
        with pytest.raises(BackupEngineError): validate_restore_destination(name)


def test_google_oauth_scope_and_safe_managed_deletion(tmp_path):
    url = authorization_url(client_id="client", redirect_uri="https://example.test/callback", scope="https://www.googleapis.com/auth/drive.file", state="signed")
    assert "drive.file" in url and "access_type=offline" in url
    responses = [{"id": "foreign", "parents": ["folder"], "appProperties": {"managedBy": "OTHER"}}]
    class Response:
        headers = {}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, *_): return json.dumps(responses.pop(0)).encode()
    adapter = GoogleDriveAdapter(client_id="c", client_secret="secret", redirect_uri="https://example.test", opener=lambda *a, **k: Response())
    with pytest.raises(GoogleDriveError, match="Refusing"): adapter.delete_managed("token", "foreign", folder_id="folder")


def test_google_rate_limit_retry_and_quota_errors():
    attempts = []
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return b'{"files":[]}'
    def opener(request, timeout):
        attempts.append(request)
        if len(attempts) < 3: raise urllib.error.HTTPError(request.full_url, 429, "rate", {}, io.BytesIO(b"rateLimitExceeded"))
        return Response()
    adapter = GoogleDriveAdapter(client_id="c", client_secret="s", redirect_uri="x", opener=opener, sleeper=lambda _: None)
    assert adapter.list_managed("token", folder_id="folder") == [] and len(attempts) == 3
    error = urllib.error.HTTPError("x", 403, "quota", {}, io.BytesIO(b"storageQuotaExceeded"))
    quota_adapter = GoogleDriveAdapter(client_id="c", client_secret="s", redirect_uri="x", opener=lambda *a, **k: (_ for _ in ()).throw(error))
    with pytest.raises(GoogleDriveQuotaError): quota_adapter.quota("token")


def test_google_upload_streams_and_retries_interruption(tmp_path):
    archive = tmp_path / "backup.icmsbak"; archive.write_bytes(b"encrypted" * 100)
    sha = hashlib.sha256(archive.read_bytes()).hexdigest(); calls = []; interrupted = {"done": False}
    class Response:
        def __init__(self, payload=b"{}", headers=None): self.payload, self.headers = payload, headers or {}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, *_): return self.payload
    def opener(request, timeout):
        calls.append(request)
        if request.full_url.startswith("https://www.googleapis.com/upload"):
            return Response(headers={"Location": "https://upload.example/session"})
        assert not isinstance(request.data, (bytes, bytearray))
        if not interrupted["done"]: interrupted["done"] = True; raise OSError("connection dropped")
        payload = json.dumps({"id": "drive-file", "size": str(archive.stat().st_size), "appProperties": {"sha256": sha}}).encode()
        return Response(payload)
    adapter = GoogleDriveAdapter(client_id="c", client_secret="s", redirect_uri="x", opener=opener, sleeper=lambda _: None)
    assert adapter.upload("token", archive, folder_id="folder", sha256=sha)["id"] == "drive-file"
    assert len(calls) == 3


def test_retention_keeps_latest_daily_and_distinct_weekly():
    jobs = [SimpleNamespace(id=uuid.uuid4(), status="VERIFIED", created_at=datetime(2026, 1, day, tzinfo=timezone.utc)) for day in range(1, 20)]
    candidates = retention_candidates(jobs, keep_daily=7, keep_weekly=2)
    kept = {x.id for x in jobs} - {x.id for x in candidates}
    assert len(kept) >= 7


def test_worker_uses_session_lock_and_persistent_retry_state():
    source = inspect.getsource(process_next_backup)
    assert "pg_try_advisory_lock" in source and "pg_try_advisory_xact_lock" not in source
    assert "RETRY_PENDING" in source and "max_attempts" in source and "pg_advisory_unlock" in source
