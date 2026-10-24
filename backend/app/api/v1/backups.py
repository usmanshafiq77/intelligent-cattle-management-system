from datetime import datetime, timedelta, timezone
from pathlib import Path
import uuid
from zoneinfo import ZoneInfo

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.admin import require_system_admin
from app.core.config import get_settings
from app.core.security import verify_password_safely
from app.db.session import get_db
from app.models.settings_backup import BackupConfiguration, BackupJob, GoogleDriveCredential, RestoreVerification
from app.models.user import User, UserStatus
from app.schemas.backup import BackupConfigChange, BackupConfigResponse, BackupJobResponse, BackupRequest, ReauthRequest, RestoreTestRequest
from app.schemas.user import MessageResponse
from app.services.backup_engine import BackupEngineError, restore_and_verify, verify_encrypted_backup
from app.services.backup_orchestrator import access_token, drive_adapter, ensure_local_copy, retention_candidates, store_drive_tokens
from app.services.google_drive import GoogleDriveError, authorization_url


router = APIRouter(prefix="/admin/backups", tags=["Platform Backup Administration"])


def _reauth(admin: User, password: str):
    if not verify_password_safely(password, admin.password_hash): raise HTTPException(status_code=403, detail="Current password is incorrect")


def _config(db: Session, admin_id=None):
    item = db.get(BackupConfiguration, 1)
    if not item: item = BackupConfiguration(id=1, updated_by_id=admin_id); db.add(item); db.commit(); db.refresh(item)
    return item


def _path(job: BackupJob) -> Path:
    settings = get_settings()
    if not job.file_name or Path(job.file_name).name != job.file_name: raise HTTPException(status_code=404, detail="Backup file is unavailable")
    root = settings.BACKUP_ROOT.resolve(); target = (root / job.file_name).resolve()
    if target.parent != root or not target.is_file(): raise HTTPException(status_code=404, detail="Backup file is unavailable")
    return target


@router.get("/dashboard")
def dashboard(admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    last_success = db.scalar(select(BackupJob).where(BackupJob.status.in_(["VERIFIED","COMPLETED_LOCALLY","RESTORE_TESTED"])).order_by(BackupJob.created_at.desc()))
    last_failure = db.scalar(select(BackupJob).where(BackupJob.status == "FAILED").order_by(BackupJob.created_at.desc()))
    credential = db.scalar(select(GoogleDriveCredential).where(GoogleDriveCredential.provider == "GOOGLE_DRIVE")); config = _config(db, admin.id)
    now = datetime.now(timezone.utc); local = now.astimezone(ZoneInfo(config.timezone)); candidate = datetime.combine(local.date(), config.daily_time, tzinfo=local.tzinfo)
    if candidate <= local: candidate += timedelta(days=1)
    return {"last_success": BackupJobResponse.model_validate(last_success) if last_success else None, "last_failure": BackupJobResponse.model_validate(last_failure) if last_failure else None, "pending": db.scalar(select(func.count()).select_from(BackupJob).where(BackupJob.status.in_(["PENDING","RETRY_PENDING","RUNNING","UPLOAD_PENDING"]))) or 0, "google_drive": "CONNECTED" if credential and not credential.revoked_at else "NOT_CONNECTED", "encryption_configured": bool(get_settings().BACKUP_ENCRYPTION_KEY), "scheduler_running": False, "schedule_enabled": config.schedule_enabled, "next_configured_run": candidate.astimezone(timezone.utc) if config.schedule_enabled else None}


@router.get("/jobs", response_model=list[BackupJobResponse])
def list_jobs(limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    return db.scalars(select(BackupJob).order_by(BackupJob.created_at.desc()).offset(offset).limit(limit)).all()


@router.get("/jobs/{job_id}", response_model=BackupJobResponse)
def get_job(job_id: uuid.UUID, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    item = db.get(BackupJob, job_id)
    if not item: raise HTTPException(status_code=404, detail="Backup job not found")
    return item


@router.post("/jobs", response_model=BackupJobResponse, status_code=202)
def request_backup(data: BackupRequest, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    _reauth(admin, data.current_password)
    existing = db.scalar(select(BackupJob).where(BackupJob.request_id == data.request_id))
    if existing: return existing
    item = BackupJob(request_id=data.request_id, backup_type=data.backup_type, status="PENDING", requested_by_id=admin.id); db.add(item); db.commit(); db.refresh(item); return item


@router.post("/jobs/{job_id}/verify", response_model=BackupJobResponse)
def verify_job(job_id: uuid.UUID, data: ReauthRequest, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    _reauth(admin, data.current_password); item = db.get(BackupJob, job_id)
    if not item or not item.encrypted_sha256: raise HTTPException(status_code=404, detail="Completed backup not found")
    item.integrity_verified = verify_encrypted_backup(_path(item), expected_sha256=item.encrypted_sha256)
    if not item.integrity_verified: item.status="FAILED"; item.error_code="INTEGRITY_MISMATCH"; item.error_summary="Encrypted backup hash did not match recorded metadata"
    db.commit(); db.refresh(item); return item


@router.post("/jobs/{job_id}/restore-test")
def restore_test(job_id: uuid.UUID, data: RestoreTestRequest, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    _reauth(admin, data.current_password); item = db.get(BackupJob, job_id)
    if not item: raise HTTPException(status_code=404, detail="Backup job not found")
    record = RestoreVerification(backup_job_id=item.id, status="RUNNING", destination=data.destination_database, verified_by_id=admin.id); db.add(record); db.commit()
    try:
        report = restore_and_verify(get_settings(), ensure_local_copy(db, item), destination_database=data.destination_database)
        expected = (item.metadata_json or {}).get("critical_counts")
        if expected is not None and report.get("critical_counts") != expected: raise BackupEngineError("Restored critical record counts do not match backup metadata")
        record.status="PASSED"; record.report_json=report; item.status="RESTORE_TESTED"
    except BackupEngineError as error: record.status="FAILED"; record.error_summary=str(error); db.commit(); raise HTTPException(status_code=422, detail=str(error)) from None
    record.completed_at=datetime.now(timezone.utc); db.commit(); return {"id": record.id, "status": record.status, "report": record.report_json}


@router.get("/restore-tests")
def restore_history(admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    return db.scalars(select(RestoreVerification).order_by(RestoreVerification.started_at.desc()).limit(100)).all()


@router.get("/configuration", response_model=BackupConfigResponse)
def get_configuration(admin: User = Depends(require_system_admin), db: Session = Depends(get_db)): return _config(db, admin.id)


@router.put("/configuration", response_model=BackupConfigResponse)
def update_configuration(data: BackupConfigChange, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    _reauth(admin,data.current_password); item=_config(db,admin.id)
    for key,value in data.model_dump(exclude={"current_password"}).items(): setattr(item,key,value)
    item.updated_by_id=admin.id; db.commit(); db.refresh(item); return item


@router.get("/retention")
def retention_report(admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    config=_config(db,admin.id); jobs=db.scalars(select(BackupJob).order_by(BackupJob.created_at.desc())).all(); candidates=retention_candidates(jobs,keep_daily=config.keep_daily,keep_weekly=config.keep_weekly)
    return {"keep_daily":config.keep_daily,"keep_weekly":config.keep_weekly,"deletion_executed":False,"candidate_ids":[str(x.id) for x in candidates]}


@router.post("/google/connect")
def connect_google(data: ReauthRequest, admin: User = Depends(require_system_admin)):
    _reauth(admin,data.current_password); settings=get_settings()
    if not settings.GOOGLE_DRIVE_CLIENT_ID or not settings.GOOGLE_DRIVE_CLIENT_SECRET: raise HTTPException(status_code=503,detail="Google Drive OAuth is not configured")
    now=datetime.now(timezone.utc); state=jwt.encode({"sub":str(admin.id),"type":"google_drive_oauth","iat":now,"exp":now+timedelta(minutes=10)},settings.JWT_SECRET_KEY.get_secret_value(),algorithm="HS256")
    return {"authorization_url":authorization_url(client_id=settings.GOOGLE_DRIVE_CLIENT_ID,redirect_uri=settings.GOOGLE_DRIVE_REDIRECT_URI,scope=settings.GOOGLE_DRIVE_OAUTH_SCOPES,state=state)}


@router.get("/google/callback", include_in_schema=False)
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    settings=get_settings()
    try:
        claims=jwt.decode(state,settings.JWT_SECRET_KEY.get_secret_value(),algorithms=["HS256"])
        admin=db.get(User,uuid.UUID(claims["sub"]))
        if claims.get("type") != "google_drive_oauth" or not admin or not admin.is_system_admin or admin.status != UserStatus.ACTIVE:
            raise ValueError("Invalid OAuth principal")
    except Exception: raise HTTPException(status_code=400,detail="Invalid or expired OAuth state") from None
    try: tokens=drive_adapter(settings).exchange_code(code); credential=store_drive_tokens(db,admin_id=admin.id,tokens=tokens,settings=settings); db.commit(); token=tokens.get("access_token"); credential.folder_id=drive_adapter(settings).ensure_folder(token,credential.folder_id); db.commit()
    except Exception: db.rollback(); return RedirectResponse(f"{settings.FRONTEND_PUBLIC_URL}/admin/backups/connection?status=failed",status_code=303)
    return RedirectResponse(f"{settings.FRONTEND_PUBLIC_URL}/admin/backups/connection?status=connected",status_code=303)


@router.get("/google/status")
def google_status(admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    item=db.scalar(select(GoogleDriveCredential).where(GoogleDriveCredential.provider=="GOOGLE_DRIVE")); return {"status":"CONNECTED" if item and not item.revoked_at else "NOT_CONNECTED","scope":item.scope if item and not item.revoked_at else None,"folder_ready":bool(item and item.folder_id and not item.revoked_at),"connected_at":item.connected_at if item and not item.revoked_at else None}


@router.get("/google/files")
def google_files(admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    item=db.scalar(select(GoogleDriveCredential).where(GoogleDriveCredential.provider=="GOOGLE_DRIVE",GoogleDriveCredential.revoked_at.is_(None)))
    if not item or not item.folder_id: raise HTTPException(status_code=409,detail="Google Drive is not connected")
    try:
        token=access_token(db,item); adapter=drive_adapter(); return {"files":adapter.list_managed(token,folder_id=item.folder_id),"storage_quota":adapter.quota(token)}
    except (BackupEngineError, GoogleDriveError) as error: raise HTTPException(status_code=503,detail=str(error)) from None


@router.post("/google/disconnect", response_model=MessageResponse)
def disconnect_google(data: ReauthRequest, admin: User = Depends(require_system_admin), db: Session = Depends(get_db)):
    _reauth(admin,data.current_password); item=db.scalar(select(GoogleDriveCredential).where(GoogleDriveCredential.provider=="GOOGLE_DRIVE"))
    if item: item.revoked_at=datetime.now(timezone.utc); db.commit()
    return MessageResponse(detail="Google Drive connection removed from ICMS. Existing Drive files were not deleted.")
