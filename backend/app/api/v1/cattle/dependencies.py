from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.cattle import (
    Breed,
    Cattle,
    CattleMedia,
    CattleWeightRecord,
)
from app.schemas.cattle import BreedResponse, CattleResponse, WeightResponse
from app.services.cattle import CattleValidationError, get_cattle_in_farm


CATTLE_PREFIX = "/farms/{farm_id}/cattle"


def validation_error(
    error: CattleValidationError | ValueError,
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=str(error),
    )


def constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def weight_response(record: CattleWeightRecord) -> WeightResponse:
    return WeightResponse.model_validate(record)


def cattle_responses(
    db: Session, animals: list[Cattle]
) -> list[CattleResponse]:
    if not animals:
        return []
    cattle_ids = [animal.id for animal in animals]
    breed_ids = {animal.breed_id for animal in animals if animal.breed_id}
    breeds = {
        breed.id: breed
        for breed in db.scalars(
            select(Breed).where(Breed.id.in_(breed_ids))
        )
    }
    ranked_weights = (
        select(
            CattleWeightRecord.id.label("weight_id"),
            func.row_number()
            .over(
                partition_by=CattleWeightRecord.cattle_id,
                order_by=(
                    CattleWeightRecord.measured_at.desc(),
                    CattleWeightRecord.id.desc(),
                ),
            )
            .label("position"),
        )
        .where(CattleWeightRecord.cattle_id.in_(cattle_ids))
        .subquery()
    )
    latest_weights = {
        record.cattle_id: record
        for record in db.scalars(
            select(CattleWeightRecord)
            .join(
                ranked_weights,
                ranked_weights.c.weight_id == CattleWeightRecord.id,
            )
            .where(ranked_weights.c.position == 1)
        )
    }
    media_counts = dict(
        db.execute(
            select(CattleMedia.cattle_id, func.count(CattleMedia.id))
            .where(
                CattleMedia.cattle_id.in_(cattle_ids),
                CattleMedia.removed_at.is_(None),
            )
            .group_by(CattleMedia.cattle_id)
        ).all()
    )
    responses = []
    for animal in animals:
        breed = breeds.get(animal.breed_id)
        latest_weight = latest_weights.get(animal.id)
        responses.append(
            CattleResponse(
                id=animal.id,
                farm_id=animal.farm_id,
                tag_number=animal.tag_number,
                name=animal.name,
                species=animal.species,
                sex=animal.sex,
                category=animal.category,
                breed=(
                    BreedResponse.model_validate(breed) if breed else None
                ),
                date_of_birth=animal.date_of_birth,
                birth_date_estimated=animal.birth_date_estimated,
                registration_date=animal.registration_date,
                acquisition_date=animal.acquisition_date,
                acquisition_method=animal.acquisition_method,
                acquisition_source=animal.acquisition_source,
                initial_acquisition_cost=animal.initial_acquisition_cost,
                initial_acquisition_currency=animal.initial_acquisition_currency,
                color=animal.color,
                identification_marks=animal.identification_marks,
                status=animal.status,
                mother_id=animal.mother_id,
                father_id=animal.father_id,
                notes=animal.notes,
                created_by_id=animal.created_by_id,
                created_at=animal.created_at,
                updated_at=animal.updated_at,
                latest_weight=(
                    weight_response(latest_weight) if latest_weight else None
                ),
                media_count=media_counts.get(animal.id, 0),
            )
        )
    return responses


def animal_or_404(
    db: Session, *, farm_id: UUID, cattle_id: UUID, lock: bool = False
) -> Cattle:
    animal = get_cattle_in_farm(
        db, farm_id=farm_id, cattle_id=cattle_id, lock=lock
    )
    if animal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cattle not found",
        )
    return animal
