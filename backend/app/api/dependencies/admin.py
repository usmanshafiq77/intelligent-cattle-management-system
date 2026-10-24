from fastapi import Depends, HTTPException, status
from app.api.v1.auth import get_current_user
from app.models.user import User


def require_system_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_system_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="System administrator access required")
    return user
