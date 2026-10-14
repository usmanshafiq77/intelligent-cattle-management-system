from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.farm import Farm
from app.models.farm_member import FarmMember, FarmRole, MemberStatus
from app.models.invitation import Invitation, InvitationStatus
from app.models.user import User, UserStatus
from app.services.invitations import generate_invitation_token


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


def create_invitation(
    db: Session,
    *,
    farm: Farm,
    invited_by: User,
    email: str,
    role: FarmRole = FarmRole.WORKER,
    status: InvitationStatus = InvitationStatus.PENDING,
    expires_at: datetime | None = None,
) -> tuple[str, Invitation]:
    raw_token, token_hash = generate_invitation_token()
    invitation = Invitation(
        farm_id=farm.id,
        invited_by_id=invited_by.id,
        email=email,
        role=role,
        token_hash=token_hash,
        status=status,
        expires_at=(
            expires_at
            or datetime.now(timezone.utc) + timedelta(days=1)
        ),
        accepted_at=(
            datetime.now(timezone.utc)
            if status == InvitationStatus.ACCEPTED
            else None
        ),
    )
    db.add(invitation)
    db.commit()
    return raw_token, invitation
