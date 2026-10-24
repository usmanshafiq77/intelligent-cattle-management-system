
import logging
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.normalization import normalize_email
from app.core.rate_limit import enforce_rate_limit
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password_safely,
)
from app.db.session import get_db
from app.models.user import User, UserStatus
from app.schemas.user import (
    EmailVerificationRequest,
    EmailVerificationResendRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
    RegistrationResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.email_delivery import EmailSender, get_email_sender
from app.services.email_verification import (
    InvalidVerificationTokenError,
    issue_verification_token,
    verify_email_token,
)
from app.services.account_settings import InvalidEmailChangeToken, verify_email_change

# NEW: Password reset service imports
from app.services.password_reset import (
    InvalidPasswordResetTokenError,
    hash_reset_token,
    issue_password_reset_token,
    reset_password_with_token,
)
from app.services.media_storage import (
    ALLOWED_IMAGE_TYPES,
    MediaStorage,
    detect_image_content_type,
    get_media_storage,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

bearer_scheme = HTTPBearer(auto_error=False)

GENERIC_RESEND_RESPONSE = (
    "If the account exists and still requires verification, "
    "a verification email will be sent."
)

VERIFICATION_REQUIRED_DETAIL = "Email verification required"


def _send_verification_email(
    sender: EmailSender,
    *,
    user: User,
    raw_token: str,
    expires_at,
) -> bool:
    try:
        sender.send_verification_email(
            recipient=user.email,
            token=raw_token,
            expires_at=expires_at,
        )
        return True
    except Exception:
        logger.exception(
            "Email verification delivery failed for user %s",
            user.id,
        )
        return False


@router.post(
    "/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    data: UserRegister,
    request: Request,
    db: Session = Depends(get_db),
    email_sender: EmailSender = Depends(get_email_sender),
):
    settings = get_settings()
    email = normalize_email(str(data.email))
    full_name = data.full_name.strip()

    enforce_rate_limit(
        request,
        scope="register",
        identity=email,
        limit=settings.REGISTER_RATE_LIMIT_REQUESTS,
        window_seconds=settings.REGISTER_RATE_LIMIT_WINDOW_SECONDS,
        enabled=settings.AUTH_RATE_LIMIT_ENABLED,
        max_keys=settings.RATE_LIMIT_MAX_KEYS,
    )

    if len(full_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Full name must contain at least 2 characters",
        )

    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    new_user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(data.password),
        is_system_admin=False,
        status=UserStatus.PENDING,
    )

    try:
        db.add(new_user)
        db.flush()

        raw_token, verification_token = issue_verification_token(
            db,
            user=new_user,
            lifetime_minutes=(
                settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
            ),
        )

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from None

    except SQLAlchemyError:
        db.rollback()
        logger.exception("User registration failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not register user",
        ) from None

    db.refresh(new_user)

    delivered = _send_verification_email(
        email_sender,
        user=new_user,
        raw_token=raw_token,
        expires_at=verification_token.expires_at,
    )

    response = UserResponse.model_validate(
        new_user,
        from_attributes=True,
    )

    return RegistrationResponse(
        **response.model_dump(),
        verification_delivery_status=(
            "SENT" if delivered else "FAILED"
        ),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_user(
    data: UserLogin,
    request: Request,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    email = normalize_email(str(data.email))

    enforce_rate_limit(
        request,
        scope="login",
        identity=email,
        limit=settings.LOGIN_RATE_LIMIT_REQUESTS,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
        enabled=settings.AUTH_RATE_LIMIT_ENABLED,
        max_keys=settings.RATE_LIMIT_MAX_KEYS,
    )

    user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    password_matches = verify_password_safely(
        data.password,
        user.password_hash if user is not None else None,
    )

    if user is None or not password_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=VERIFICATION_REQUIRED_DETAIL,
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    return TokenResponse(
        access_token=create_access_token(
            user.id,
            token_version=user.token_version,
        ),
        token_type="bearer",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise authentication_error

    try:
        payload = decode_access_token(credentials.credentials)

        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        user_id = UUID(payload["sub"])

    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise authentication_error from None

    user = db.get(User, user_id)

    if user is None:
        raise authentication_error

    # Reject JWTs issued before a password reset.
    token_version = payload.get("token_version", 0)

    if (
        type(token_version) is not int
        or token_version != user.token_version
    ):
        raise authentication_error

    if user.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=VERIFICATION_REQUIRED_DETAIL,
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    return user


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    return current_user


def _avatar_storage_key(user: User) -> str:
    return f"avatars/{user.id}.image"


async def _read_avatar_body(request: Request, maximum: int) -> bytes:
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > maximum:
            raise HTTPException(status_code=413, detail="Profile image is too large")
        content.extend(chunk)
    return bytes(content)


@router.get("/me/avatar", response_class=FileResponse)
def get_my_avatar(
    current_user: User = Depends(get_current_user),
    storage: MediaStorage = Depends(get_media_storage),
):
    try:
        path = storage.resolve(_avatar_storage_key(current_user))
        with path.open("rb") as stream:
            content_type = detect_image_content_type(stream.read(16))
    except (FileNotFoundError, ValueError, OSError):
        raise HTTPException(status_code=404, detail="Profile image not found") from None
    return FileResponse(path=path, media_type=content_type)


@router.put("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
async def upload_my_avatar(
    request: Request,
    current_user: User = Depends(get_current_user),
    storage: MediaStorage = Depends(get_media_storage),
):
    maximum = get_settings().PROFILE_AVATAR_MAX_BYTES
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_length = int(content_length)
            if declared_length < 0:
                raise ValueError
            if declared_length > maximum:
                raise HTTPException(status_code=413, detail="Profile image is too large")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from None
    content = await _read_avatar_body(request, maximum)
    if not content:
        raise HTTPException(status_code=422, detail="Profile image content is required")
    try:
        detected_type = detect_image_content_type(content)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    declared_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if declared_type not in {detected_type, "application/octet-stream"}:
        raise HTTPException(status_code=422, detail="Declared content type does not match image content")
    if detected_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported profile image type")
    try:
        storage.save(_avatar_storage_key(current_user), content)
    except (OSError, ValueError):
        logger.exception("Profile image upload failed for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Could not store profile image") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/me/avatar", status_code=status.HTTP_204_NO_CONTENT)
def remove_my_avatar(
    current_user: User = Depends(get_current_user),
    storage: MediaStorage = Depends(get_media_storage),
):
    try:
        storage.delete(_avatar_storage_key(current_user))
    except (OSError, ValueError):
        logger.exception("Profile image removal failed for user %s", current_user.id)
        raise HTTPException(status_code=500, detail="Could not remove profile image") from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/verify-email",
    response_model=MessageResponse,
)
def verify_email(
    data: EmailVerificationRequest,
    db: Session = Depends(get_db),
):
    try:
        verify_email_token(
            db,
            raw_token=data.token,
        )
        db.commit()

    except InvalidVerificationTokenError:
        db.rollback()
        try:
            verify_email_change(db, data.token)
            db.commit()
            return MessageResponse(detail="Email address changed and verified successfully. Please log in again.")
        except InvalidEmailChangeToken:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token is invalid or expired") from None

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Email verification failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify email",
        ) from None

    return MessageResponse(
        detail="Email verified successfully"
    )


@router.post(
    "/verification/resend",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_email_verification(
    data: EmailVerificationResendRequest,
    request: Request,
    db: Session = Depends(get_db),
    email_sender: EmailSender = Depends(get_email_sender),
):
    settings = get_settings()
    email = normalize_email(str(data.email))

    enforce_rate_limit(
        request,
        scope="verification-resend",
        identity=email,
        limit=settings.VERIFICATION_RESEND_RATE_LIMIT_REQUESTS,
        window_seconds=(
            settings.VERIFICATION_RESEND_RATE_LIMIT_WINDOW_SECONDS
        ),
        enabled=settings.AUTH_RATE_LIMIT_ENABLED,
        max_keys=settings.RATE_LIMIT_MAX_KEYS,
    )

    user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    if user is None or user.email_verified_at is not None:
        return MessageResponse(
            detail=GENERIC_RESEND_RESPONSE
        )

    try:
        raw_token, verification_token = issue_verification_token(
            db,
            user=user,
            lifetime_minutes=(
                settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
            ),
        )

        db.commit()

    except IntegrityError:
        db.rollback()
        return MessageResponse(
            detail=GENERIC_RESEND_RESPONSE
        )

    except SQLAlchemyError:
        db.rollback()
        logger.exception("Email verification resend failed")
        return MessageResponse(
            detail=GENERIC_RESEND_RESPONSE
        )

    _send_verification_email(
        email_sender,
        user=user,
        raw_token=raw_token,
        expires_at=verification_token.expires_at,
    )

    return MessageResponse(
        detail=GENERIC_RESEND_RESPONSE
    )



# =====================================================
# FORGOT PASSWORD
# =====================================================

GENERIC_PASSWORD_RESET_RESPONSE = (
    "If the account is eligible, password reset "
    "instructions will be sent."
)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    email_sender: EmailSender = Depends(get_email_sender),
):
    settings = get_settings()
    email = normalize_email(str(data.email))

    enforce_rate_limit(
        request,
        scope="forgot-password",
        identity=email,
        limit=settings.FORGOT_PASSWORD_RATE_LIMIT_REQUESTS,
        window_seconds=settings.FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS,
        enabled=settings.AUTH_RATE_LIMIT_ENABLED,
        max_keys=settings.RATE_LIMIT_MAX_KEYS,
    )

    user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    # Do not reveal whether an email belongs to an account.
    if (
        user is None
        or user.status != UserStatus.ACTIVE
        or user.email_verified_at is None
    ):
        return MessageResponse(
            detail=GENERIC_PASSWORD_RESET_RESPONSE
        )

    try:
        raw_token, reset_token = issue_password_reset_token(
            db,
            user=user,
            lifetime_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
        )
        db.commit()

    except Exception:
        db.rollback()
        logger.exception("Password reset request failed")
        return MessageResponse(
            detail=GENERIC_PASSWORD_RESET_RESPONSE
        )

    try:
        email_sender.send_password_reset_email(
            recipient=user.email,
            token=raw_token,
            expires_at=reset_token.expires_at,
        )
    except Exception:
        # Avoid revealing delivery or account status.
        logger.exception(
            "Password reset delivery failed for user %s",
            user.id,
        )

    return MessageResponse(
        detail=GENERIC_PASSWORD_RESET_RESPONSE
    )


# =====================================================
# RESET PASSWORD
# =====================================================

@router.post(
    "/reset-password",
    response_model=MessageResponse,
)
def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    settings = get_settings()

    # Rate limit repeated reset attempts.
    enforce_rate_limit(
        request,
        scope="reset-password",
        identity=hash_reset_token(data.token),
        limit=settings.RESET_PASSWORD_RATE_LIMIT_REQUESTS,
        window_seconds=settings.RESET_PASSWORD_RATE_LIMIT_WINDOW_SECONDS,
        enabled=settings.AUTH_RATE_LIMIT_ENABLED,
        max_keys=settings.RATE_LIMIT_MAX_KEYS,
    )

    try:
        reset_password_with_token(
            db,
            raw_token=data.token,
            new_password=data.new_password,
        )
        db.commit()

    except InvalidPasswordResetTokenError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link is invalid or expired",
        ) from None

    except Exception:
        db.rollback()
        logger.exception("Password reset failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not reset password",
        ) from None

    return MessageResponse(
        detail="Password reset successfully. Please log in again."
    )
