import hashlib
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.services.backup_crypto import decode_key, decrypt_file, encrypt_file


class BackupEngineError(RuntimeError): pass


CRITICAL_TABLES = ("users", "farms", "farm_members", "cattle")


def _database_metadata(settings: Settings, database_name: str) -> dict:
    from sqlalchemy import URL, create_engine, inspect, text
    engine = create_engine(URL.create("postgresql+psycopg", username=settings.DB_USER, password=settings.DB_PASSWORD.get_secret_value(), host=settings.DB_HOST, port=settings.DB_PORT, database=database_name), pool_pre_ping=True, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names(schema="public"))
            counts = {name: connection.scalar(text(f'SELECT count(*) FROM "{name}"')) for name in CRITICAL_TABLES if name in tables}
            return {"database": connection.scalar(text("SELECT current_database()")), "server_version_num": connection.scalar(text("SHOW server_version_num")), "table_count": len(tables), "critical_counts": counts}
    finally: engine.dispose()


def _safe_root(settings: Settings) -> Path:
    root = settings.BACKUP_ROOT.resolve(); root.mkdir(parents=True, exist_ok=True); os.chmod(root, 0o700); return root


def create_database_backup(settings: Settings, *, now: datetime | None = None, runner=subprocess.run, metadata_loader=_database_metadata) -> dict:
    if not settings.BACKUP_ENCRYPTION_KEY: raise BackupEngineError("Backup encryption key is not configured")
    key = decode_key(settings.BACKUP_ENCRYPTION_KEY.get_secret_value()); root = _safe_root(settings); stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S%fZ")
    final = root / f"icms_database_{stamp}.dump.icmsbak"; partial = final.with_suffix(final.suffix + ".part")
    env = os.environ.copy(); env["PGPASSWORD"] = settings.DB_PASSWORD.get_secret_value()
    with tempfile.TemporaryDirectory(prefix="icms-backup-") as temp:
        os.chmod(temp, 0o700); plain = Path(temp) / "database.dump"
        try:
            command = [settings.PG_DUMP_PATH, "--host", settings.DB_HOST, "--port", str(settings.DB_PORT), "--username", settings.DB_USER, "--dbname", settings.DB_NAME, "--format", "custom", "--compress", "9", "--no-owner", "--no-privileges", "--file", str(plain)]
            result = runner(command, env=env, capture_output=True, text=True, timeout=3600, check=False)
            if result.returncode != 0 or not plain.is_file() or plain.stat().st_size == 0: raise BackupEngineError("pg_dump did not produce a valid archive")
            verify = runner([settings.PG_RESTORE_PATH, "--list", str(plain)], env=env, capture_output=True, text=True, timeout=300, check=False)
            if verify.returncode != 0: raise BackupEngineError("pg_restore could not validate the archive catalog")
            database_meta = metadata_loader(settings, settings.DB_NAME)
            result_meta = encrypt_file(plain, partial, key=key, key_id=settings.BACKUP_KEY_ID); os.replace(partial, final)
            return {**result_meta, **database_meta, "path": final, "file_name": final.name, "created_at": (now or datetime.now(timezone.utc)).isoformat()}
        finally:
            partial.unlink(missing_ok=True); plain.unlink(missing_ok=True)


def verify_encrypted_backup(path: Path, *, expected_sha256: str) -> bool:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024): digest.update(chunk)
    return digest.hexdigest() == expected_sha256


def validate_restore_destination(database_name: str) -> None:
    if database_name in {"icms_db", "icms_test"} or not (database_name.startswith("test_restore_") or database_name.endswith("_restore_test")): raise BackupEngineError("Restore destination must be a dedicated disposable recovery-test database")


def decrypt_and_validate_archive(settings: Settings, encrypted_path: Path, *, destination_database: str, runner=subprocess.run) -> dict:
    validate_restore_destination(destination_database)
    if not settings.BACKUP_ENCRYPTION_KEY: raise BackupEngineError("Backup recovery key is unavailable")
    with tempfile.TemporaryDirectory(prefix="icms-restore-check-") as temp:
        os.chmod(temp, 0o700); plain = Path(temp) / "archive.dump"
        metadata = decrypt_file(encrypted_path, plain, keys={settings.BACKUP_KEY_ID: decode_key(settings.BACKUP_ENCRYPTION_KEY.get_secret_value())})
        check = runner([settings.PG_RESTORE_PATH, "--list", str(plain)], capture_output=True, text=True, timeout=300, check=False)
        if check.returncode != 0: raise BackupEngineError("Decrypted archive catalog is invalid")
        return {**metadata, "archive_valid": True, "destination_database": destination_database}


def restore_and_verify(settings: Settings, encrypted_path: Path, *, destination_database: str, runner=subprocess.run) -> dict:
    validate_restore_destination(destination_database)
    if not settings.BACKUP_ENCRYPTION_KEY: raise BackupEngineError("Backup recovery key is unavailable")
    env = os.environ.copy(); env["PGPASSWORD"] = settings.DB_PASSWORD.get_secret_value()
    with tempfile.TemporaryDirectory(prefix="icms-restore-") as temp:
        os.chmod(temp, 0o700); plain = Path(temp) / "archive.dump"
        metadata = decrypt_file(encrypted_path, plain, keys={settings.BACKUP_KEY_ID: decode_key(settings.BACKUP_ENCRYPTION_KEY.get_secret_value())})
        catalog = runner([settings.PG_RESTORE_PATH, "--list", str(plain)], env=env, capture_output=True, text=True, timeout=300, check=False)
        if catalog.returncode != 0: raise BackupEngineError("Decrypted archive catalog is invalid")
        restored = runner([settings.PG_RESTORE_PATH, "--exit-on-error", "--no-owner", "--no-privileges", "--host", settings.DB_HOST, "--port", str(settings.DB_PORT), "--username", settings.DB_USER, "--dbname", destination_database, str(plain)], env=env, capture_output=True, text=True, timeout=3600, check=False)
        if restored.returncode != 0: raise BackupEngineError("Restore into the isolated recovery-test database failed")
        from sqlalchemy import URL, create_engine, inspect, text
        engine = create_engine(URL.create("postgresql+psycopg", username=settings.DB_USER, password=settings.DB_PASSWORD.get_secret_value(), host=settings.DB_HOST, port=settings.DB_PORT, database=destination_database), pool_pre_ping=True, connect_args={"connect_timeout": 5})
        try:
            with engine.connect() as connection:
                actual = connection.scalar(text("SELECT current_database()")); tables = set(inspect(connection).get_table_names(schema="public")); table_count = len(tables); revision = connection.scalar(text("SELECT version_num FROM alembic_version")); counts = {name: connection.scalar(text(f'SELECT count(*) FROM "{name}"')) for name in CRITICAL_TABLES if name in tables}; server_version = connection.scalar(text("SHOW server_version_num"))
            if actual != destination_database or table_count < 1: raise BackupEngineError("Restored database identity or table verification failed")
            return {**metadata, "archive_valid": True, "destination_database": actual, "table_count": table_count, "alembic_revision": revision, "critical_counts": counts, "server_version_num": server_version}
        finally: engine.dispose()
