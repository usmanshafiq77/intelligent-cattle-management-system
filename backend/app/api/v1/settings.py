from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import require_farm_permission
from app.api.v1.auth import get_current_user
from app.core.permissions import Permission
from app.core.security import hash_password, verify_password_safely
from app.db.session import get_db
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.settings_backup import AccountDeletionRequest, FarmPreference, SecurityEvent, UserPreference
from app.models.user import User, UserStatus
from app.schemas.settings import FarmPreferenceResponse, FarmPreferenceUpdate
from app.schemas.user import AccountDeletionCreate, EmailChangeRequest, MessageResponse, PasswordChange, ProfileUpdate, ReauthenticateRequest, SecurityEventResponse, UserPreferenceResponse, UserPreferenceUpdate, UserResponse
from app.services.account_settings import issue_email_change
from app.services.email_delivery import EmailSender, get_email_sender


router = APIRouter(tags=["User and Farm Settings"])


def audit(db, user_id, event_type, summary): db.add(SecurityEvent(user_id=user_id, event_type=event_type, summary=summary, metadata_json={}))
def require_password(user, password):
    if not verify_password_safely(password, user.password_hash): raise HTTPException(status_code=403, detail="Current password is incorrect")


@router.patch("/auth/me", response_model=UserResponse)
def update_profile(data: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.full_name = " ".join(data.full_name.split()); audit(db, user.id, "PROFILE_UPDATED", "Personal profile updated"); db.commit(); db.refresh(user); return user


@router.get("/auth/me/preferences", response_model=UserPreferenceResponse)
def get_user_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(UserPreference, user.id)
    if not item: item = UserPreference(user_id=user.id); db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/auth/me/preferences", response_model=UserPreferenceResponse)
def update_user_preferences(data: UserPreferenceUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(UserPreference, user.id) or UserPreference(user_id=user.id)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    db.add(item); db.commit(); db.refresh(item); return item


@router.post("/auth/me/change-password", response_model=MessageResponse)
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_password(user, data.current_password)
    if verify_password_safely(data.new_password, user.password_hash): raise HTTPException(status_code=422, detail="New password must differ from the current password")
    user.password_hash = hash_password(data.new_password); user.token_version += 1; audit(db, user.id, "PASSWORD_CHANGED", "Password changed and existing sessions revoked"); db.commit(); return MessageResponse(detail="Password changed. Please log in again.")


@router.post("/auth/me/email-change", response_model=MessageResponse, status_code=202)
def request_email_change(data: EmailChangeRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db), sender: EmailSender = Depends(get_email_sender)):
    require_password(user, data.current_password)
    try: raw, record = issue_email_change(db, user=user, new_email=str(data.new_email)); audit(db, user.id, "EMAIL_CHANGE_REQUESTED", "Email change verification requested"); db.commit()
    except ValueError as error: db.rollback(); raise HTTPException(status_code=409, detail=str(error)) from None
    try: sender.send_verification_email(recipient=record.new_email, token=raw, expires_at=record.expires_at)
    except Exception: raise HTTPException(status_code=503, detail="Email change was saved but verification delivery failed") from None
    return MessageResponse(detail="Verification was sent to the new email address.")


@router.post("/auth/me/revoke-sessions", response_model=MessageResponse)
def revoke_sessions(data: ReauthenticateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_password(user, data.current_password); user.token_version += 1; audit(db, user.id, "SESSIONS_REVOKED", "All access tokens revoked"); db.commit(); return MessageResponse(detail="All sessions were revoked. Please log in again.")


@router.get("/auth/me/security-events", response_model=list[SecurityEventResponse])
def security_events(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(SecurityEvent).where(SecurityEvent.user_id == user.id).order_by(SecurityEvent.created_at.desc()).limit(100)).all()


@router.post("/auth/me/deactivate", response_model=MessageResponse)
def deactivate_account(data: ReauthenticateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_password(user, data.current_password)
    owned = db.scalar(select(FarmMember.id).where(FarmMember.user_id == user.id, FarmMember.role == FarmRole.FARM_OWNER, FarmMember.status == MemberStatus.ACTIVE))
    if owned: raise HTTPException(status_code=409, detail="Transfer or close owned farms before deactivating the account")
    audit(db, user.id, "ACCOUNT_DEACTIVATED", "Account voluntarily deactivated"); user.status = UserStatus.INACTIVE; user.token_version += 1; db.commit(); return MessageResponse(detail="Account deactivated.")


@router.post("/auth/me/deletion-request", response_model=MessageResponse, status_code=202)
def request_deletion(data: AccountDeletionCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_password(user, data.current_password)
    request = db.get(AccountDeletionRequest, user.id)
    if request and request.status == "REQUESTED": return MessageResponse(detail="Account deletion request is already under review.")
    if request: request.status="REQUESTED"; request.reason=data.reason; request.requested_at=datetime.now(timezone.utc); request.resolved_at=None
    else: db.add(AccountDeletionRequest(user_id=user.id, reason=data.reason))
    audit(db, user.id, "ACCOUNT_DELETION_REQUESTED", "Account deletion review requested"); db.commit(); return MessageResponse(detail="Account deletion request submitted for review. Farm and audit records were not deleted.")


@router.get("/farms/{farm_id}/settings", response_model=FarmPreferenceResponse)
def get_farm_settings(farm_id: UUID, access: FarmAccess = Depends(require_farm_permission(Permission.FARM_VIEW)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(FarmPreference, farm_id)
    if not item: item = FarmPreference(farm_id=farm_id, updated_by_id=user.id); db.add(item); db.commit(); db.refresh(item)
    return item


@router.put("/farms/{farm_id}/settings", response_model=FarmPreferenceResponse)
def update_farm_settings(farm_id: UUID, data: FarmPreferenceUpdate, access: FarmAccess = Depends(require_farm_permission(Permission.FARM_MANAGE)), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(FarmPreference, farm_id) or FarmPreference(farm_id=farm_id, updated_by_id=user.id)
    for key, value in data.model_dump().items(): setattr(item, key, value)
    item.updated_by_id = user.id; db.add(item); audit(db, user.id, "FARM_SETTINGS_UPDATED", f"Farm settings updated for {farm_id}"); db.commit(); db.refresh(item); return item
