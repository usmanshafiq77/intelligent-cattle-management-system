
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User, UserStatus
from app.schemas.user import UserRegister, UserResponse


from uuid import UUID

import jwt
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import (
    create_access_token,
    decode_access_token,
    verify_password,
)

from app.schemas.user import UserLogin, TokenResponse


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    data: UserRegister,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()
    full_name = data.full_name.strip()

    if len(full_name) < 2:
        raise HTTPException(
            status_code=422,
            detail="Full name must contain at least 2 characters",
        )

    existing_user = db.scalar(
        select(User).where(
            func.lower(User.email) == email
        )
    )

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        )

    new_user = User(
        full_name=full_name,
        email=email,
        password_hash=hash_password(data.password),
        is_system_admin=False,
        status=UserStatus.ACTIVE,
    )

    db.add(new_user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Email already registered",
        ) from None

    db.refresh(new_user)

    return new_user



# JWT Bearer Authentication
bearer_scheme = HTTPBearer(auto_error=False)


@router.post(
    "/login",
    response_model=TokenResponse,
)
def login_user(
    data: UserLogin,
    db: Session = Depends(get_db),
):
    email = str(data.email).strip().lower()

    user = db.scalar(
        select(User).where(
            func.lower(User.email) == email
        )
    )

    if user is None or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=403,
            detail="User account is not active",
        )

    access_token = create_access_token(user.id)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:

    authentication_error = HTTPException(
        status_code=401,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise authentication_error

    try:
        payload = decode_access_token(
            credentials.credentials
        )

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
            status_code=403,
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
