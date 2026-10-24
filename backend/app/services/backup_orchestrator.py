import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.settings_backup import BackupConfiguration, BackupJob, GoogleDriveCredential
from app.models.user import User, UserStatus
from app.models.work_management import AppNotification
from app.services.backup_crypto import BackupCryptoError, decode_key
from app.services.backup_engine import BackupEngineError, create_database_backup, verify_encrypted_backup
from app.services.google_drive import GoogleDriveAdapter, GoogleDriveError
from app.services.secret_box import open_sealed, seal

logger = logging.getLogger(__name__)
BACKUP_LOCK = 724_918_411
TOKEN_CONTEXT = b"icms-google-drive-oauth-v1"


def enqueue_scheduled_backup(db: Session, *, now: datetime | None = None) -> BackupJob | None:
    config = db.get(BackupConfiguration, 1)
    if not config or not config.schedule_enabled: return None
    now = now or datetime.now(timezone.utc); local = now.astimezone(ZoneInfo(config.timezone))
    if local.time().replace(tzinfo=None) < config.daily_time: return None
    backup_type = "WEEKLY" if local.weekday() == 6 else "DAILY"
    request_id = uuid.uuid5(uuid.NAMESPACE_URL, f"icms-backup:{local.date()}:{backup_type}")
    existing = db.scalar(select(BackupJob).where(BackupJob.request_id == request_id))
    if existing: return existing
    job = BackupJob(request_id=request_id, backup_type=backup_type, status="PENDING", requested_by_id=None); db.add(job); db.commit(); db.refresh(job); return job


def drive_adapter(settings=None):
    settings = settings or get_settings()
    if not settings.GOOGLE_DRIVE_CLIENT_ID or not settings.GOOGLE_DRIVE_CLIENT_SECRET: raise BackupEngineError("Google Drive OAuth is not configured")
    return GoogleDriveAdapter(client_id=settings.GOOGLE_DRIVE_CLIENT_ID, client_secret=settings.GOOGLE_DRIVE_CLIENT_SECRET.get_secret_value(), redirect_uri=settings.GOOGLE_DRIVE_REDIRECT_URI, timeout=settings.GOOGLE_DRIVE_TIMEOUT_SECONDS)


def store_drive_tokens(db: Session, *, admin_id, tokens: dict, settings=None):
    settings = settings or get_settings()
    if not settings.BACKUP_ENCRYPTION_KEY or not tokens.get("refresh_token"): raise BackupEngineError("Recovery key or Google refresh token is unavailable")
    key = decode_key(settings.BACKUP_ENCRYPTION_KEY.get_secret_value()); item = db.scalar(select(GoogleDriveCredential).where(GoogleDriveCredential.provider == "GOOGLE_DRIVE"))
    if not item: item = GoogleDriveCredential(provider="GOOGLE_DRIVE", encrypted_refresh_token=b"", scope=tokens.get("scope", settings.GOOGLE_DRIVE_OAUTH_SCOPES), connected_by_id=admin_id); db.add(item)
    item.encrypted_refresh_token = seal(tokens["refresh_token"], key, context=TOKEN_CONTEXT); item.encrypted_access_token = seal(tokens["access_token"], key, context=TOKEN_CONTEXT) if tokens.get("access_token") else None
    item.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600))); item.scope = tokens.get("scope", settings.GOOGLE_DRIVE_OAUTH_SCOPES); item.connected_by_id = admin_id; item.revoked_at = None
    return item


def access_token(db: Session, credential: GoogleDriveCredential, *, settings=None) -> str:
    settings = settings or get_settings(); key = decode_key(settings.BACKUP_ENCRYPTION_KEY.get_secret_value()); adapter = drive_adapter(settings)
    if credential.revoked_at: raise BackupEngineError("Google Drive authorization was revoked")
    if credential.encrypted_access_token and credential.token_expires_at and credential.token_expires_at > datetime.now(timezone.utc) + timedelta(minutes=2): return open_sealed(credential.encrypted_access_token, key, context=TOKEN_CONTEXT)
    refresh = open_sealed(credential.encrypted_refresh_token, key, context=TOKEN_CONTEXT); tokens = adapter.refresh_access_token(refresh)
    credential.encrypted_access_token = seal(tokens["access_token"], key, context=TOKEN_CONTEXT); credential.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens.get("expires_in", 3600))); db.flush(); return tokens["access_token"]


def ensure_local_copy(db: Session, job: BackupJob, *, settings=None) -> Path:
    """Return a verified local archive, downloading only its recorded managed Drive object when needed."""
    settings = settings or get_settings(); root = settings.BACKUP_ROOT.resolve(); root.mkdir(parents=True, exist_ok=True); os.chmod(root, 0o700)
    if job.file_name and Path(job.file_name).name == job.file_name:
        existing = (root / job.file_name).resolve()
        if existing.parent == root and existing.is_file() and job.encrypted_sha256 and verify_encrypted_backup(existing, expected_sha256=job.encrypted_sha256): return existing
    if not job.drive_file_id or not job.encrypted_sha256: raise BackupEngineError("No verified local or cloud backup artifact is available")
    credential = db.scalar(select(GoogleDriveCredential).where(GoogleDriveCredential.provider == "GOOGLE_DRIVE", GoogleDriveCredential.revoked_at.is_(None)))
    if not credential or not credential.folder_id: raise BackupEngineError("Google Drive authorization is unavailable")
    final = (root / f"icms_cloud_{job.id}.dump.icmsbak").resolve(); partial = final.with_suffix(final.suffix + ".part")
    if final.parent != root: raise BackupEngineError("Backup destination is invalid")
    partial.unlink(missing_ok=True)
    try:
        token = access_token(db, credential, settings=settings); drive_adapter(settings).download(token, job.drive_file_id, partial)
        os.chmod(partial, 0o600)
        if not verify_encrypted_backup(partial, expected_sha256=job.encrypted_sha256): raise BackupEngineError("Downloaded cloud backup failed SHA-256 verification")
        os.replace(partial, final); job.file_name = final.name; job.local_available = True; job.integrity_verified = True; db.commit(); return final
    finally: partial.unlink(missing_ok=True)


def process_next_backup(db: Session, *, settings=None) -> BackupJob | None:
    settings = settings or get_settings()
    # A session lock survives the commits needed to persist job progress. An
    # xact lock would be released as soon as RUNNING is committed, allowing a
    # second worker to overlap pg_dump/upload work.
    if not db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": BACKUP_LOCK}):
        return None
    job = None
    try:
        now = datetime.now(timezone.utc)
        job = db.scalar(select(BackupJob).where(BackupJob.status.in_(["PENDING", "RETRY_PENDING"]), (BackupJob.next_attempt_at.is_(None) | (BackupJob.next_attempt_at <= now))).order_by(BackupJob.created_at).with_for_update(skip_locked=True))
        if not job:
            return None
        job.status = "RUNNING"; job.started_at = now; job.attempt_count += 1; job.next_attempt_at = None; db.commit()
        result = create_database_backup(settings)
        job.file_name = result["file_name"]; job.size_bytes = result["size_bytes"]; job.plaintext_sha256 = result["plaintext_sha256"]; job.encrypted_sha256 = result["encrypted_sha256"]; job.local_available = True; job.integrity_verified = verify_encrypted_backup(result["path"], expected_sha256=result["encrypted_sha256"]); job.status = "COMPLETED_LOCALLY"; job.metadata_json = {"database": result["database"], "key_id": result["key_id"], "database_only": True, "server_version_num": result["server_version_num"], "table_count": result["table_count"], "critical_counts": result["critical_counts"]}; db.commit()
        credential = db.scalar(select(GoogleDriveCredential).where(GoogleDriveCredential.provider == "GOOGLE_DRIVE", GoogleDriveCredential.revoked_at.is_(None)))
        if not credential: return job
        job.status = "UPLOAD_PENDING"; db.commit(); token = access_token(db, credential, settings=settings); adapter = drive_adapter(settings); folder = adapter.ensure_folder(token, credential.folder_id); credential.folder_id = folder
        uploaded = adapter.upload(token, result["path"], folder_id=folder, sha256=result["encrypted_sha256"]); job.drive_file_id = uploaded["id"]; job.status = "VERIFIED"; job.completed_at = datetime.now(timezone.utc); db.commit(); return job
    except Exception as error:
        db.rollback()
        if job is None: raise
        job = db.get(BackupJob, job.id); job.error_code = type(error).__name__[:50]; job.error_summary = (str(error) if isinstance(error, (BackupEngineError, BackupCryptoError, GoogleDriveError)) else "Unexpected backup worker error")[:500]
        if job.attempt_count < job.max_attempts:
            job.status = "RETRY_PENDING"; job.next_attempt_at = datetime.now(timezone.utc) + timedelta(minutes=2 ** job.attempt_count)
        else:
            job.status = "FAILED"; job.completed_at = datetime.now(timezone.utc)
            admin_ids = db.scalars(select(User.id).where(User.is_system_admin.is_(True), User.status == UserStatus.ACTIVE)).all()
            for admin_id in admin_ids:
                db.add(AppNotification(user_id=admin_id, farm_id=None, category="BACKUP", title="Platform backup failed", message="A platform backup exhausted its retry policy. Review Backup Alerts.", source_type="BACKUP_JOB", source_id=job.id, route="/admin/backups/alerts", idempotency_key=f"backup-failed:{job.id}:{job.attempt_count}:{admin_id}"))
        db.commit(); logger.exception("Backup job attempt failed", extra={"backup_job_id": str(job.id), "attempt": job.attempt_count}); return job
    finally:
        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": BACKUP_LOCK})


def retention_candidates(jobs: list[BackupJob], *, keep_daily: int, keep_weekly: int) -> list[BackupJob]:
    successful = [x for x in jobs if x.status in {"VERIFIED", "COMPLETED_LOCALLY", "RESTORE_TESTED"}]
    successful.sort(key=lambda x: x.created_at, reverse=True); kept, candidates, weeks = set(), [], set()
    for job in successful[:keep_daily]: kept.add(job.id)
    for job in successful:
        week = job.created_at.isocalendar()[:2]
        if week not in weeks and len(weeks) < keep_weekly: weeks.add(week); kept.add(job.id)
    for job in successful:
        if job.id not in kept: candidates.append(job)
    return candidates
