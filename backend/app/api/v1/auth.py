import logging
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    MessageResponse,
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


def _send_verification_email(
    sender: EmailSender,
    *,
    user: User,
    raw_token: str,
    expires_at,
) -> None:
    try:
        sender.send_verification_email(
            recipient=user.email,
            token=raw_token,
            expires_at=expires_at,
        )
    except Exception:
        logger.exception(
            "Email verification delivery failed for user %s",
            user.id,
        )


@router.post(
    "/register",
    response_model=UserResponse,
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
        status=UserStatus.ACTIVE,
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
    _send_verification_email(
        email_sender,
        user=new_user,
        raw_token=raw_token,
        expires_at=verification_token.expires_at,
    )
    return new_user


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

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )

    return TokenResponse(
        access_token=create_access_token(user.id),
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


@router.post(
    "/verify-email",
    response_model=MessageResponse,
)
def verify_email(
    data: EmailVerificationRequest,
    db: Session = Depends(get_db),
):
    try:
        verify_email_token(db, raw_token=data.token)
        db.commit()
    except InvalidVerificationTokenError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification token is invalid or expired",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Email verification failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not verify email",
        ) from None

    return MessageResponse(detail="Email verified successfully")


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
        return MessageResponse(detail=GENERIC_RESEND_RESPONSE)

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
        return MessageResponse(detail=GENERIC_RESEND_RESPONSE)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Email verification resend failed")
        return MessageResponse(detail=GENERIC_RESEND_RESPONSE)

    _send_verification_email(
        email_sender,
        user=user,
        raw_token=raw_token,
        expires_at=verification_token.expires_at,
    )
    return MessageResponse(detail=GENERIC_RESEND_RESPONSE)
