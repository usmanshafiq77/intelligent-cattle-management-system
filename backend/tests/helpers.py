from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.farm import Farm
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.user import User, UserStatus


def create_user(
    db: Session,
    *,
    email: str,
    password: str = "ValidPassword123!",
    status: UserStatus = UserStatus.ACTIVE,
    verified: bool = True,
) -> User:
    user = User(
        full_name="Test User",
        email=email,
        password_hash=hash_password(password),
        status=status,
        is_system_admin=False,
        email_verified_at=(
            datetime.now(timezone.utc) if verified else None
        ),
    )
    db.add(user)
    db.commit()
    return user


def authorization_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def create_owned_farm(
    db: Session,
    *,
    owner: User,
    name: str = "Test Farm",
) -> Farm:
    farm = Farm(name=name, owner_id=owner.id)
    db.add(farm)
    db.flush()
    db.add(
        FarmMember(
            farm_id=farm.id,
            user_id=owner.id,
            role=FarmRole.FARM_OWNER,
            status=MemberStatus.ACTIVE,
        )
    )
    db.commit()
    return farm
