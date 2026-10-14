from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import get_current_user
from app.db.session import get_db
from app.models.cattle import Breed, Species
from app.models.user import User
from app.schemas.cattle import BreedCreate, BreedResponse
from app.services.cattle import normalize_identity


router = APIRouter(prefix="/breeds", tags=["Cattle Breeds"])


@router.get("", response_model=list[BreedResponse])
def list_breeds(
    species: Species | None = None,
    search: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(Breed).where(Breed.is_active.is_(True))
    if species is not None:
        statement = statement.where(Breed.species == species)
    if search:
        statement = statement.where(Breed.name.ilike(f"%{search.strip()}%"))
    return db.scalars(
        statement.order_by(Breed.species, func.lower(Breed.name), Breed.id)
        .limit(limit)
        .offset(offset)
    ).all()


@router.get("/{breed_id}", response_model=BreedResponse)
def get_breed(
    breed_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    breed = db.scalar(
        select(Breed).where(Breed.id == breed_id, Breed.is_active.is_(True))
    )
    if breed is None:
        raise HTTPException(status_code=404, detail="Breed not found")
    return breed


@router.post(
    "", response_model=BreedResponse, status_code=status.HTTP_201_CREATED
)
def create_breed(
    data: BreedCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Only a system administrator may manage the global breed "
                "catalog"
            ),
        )
    breed = Breed(
        species=data.species,
        name=data.name,
        normalized_name=normalize_identity(data.name),
        description=data.description,
        created_by_id=current_user.id,
    )
    try:
        db.add(breed)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This breed already exists for the selected species",
        ) from None
    db.refresh(breed)
    return breed
