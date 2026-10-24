from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.farms import FarmAccess
from app.api.dependencies.permissions import (
    require_farm_permission,
    require_veterinarian_permission,
)
from app.api.v1.auth import get_current_user
from app.api.v1.health.dependencies import (
    HEALTH_PREFIX,
    commit_or_error,
    validation_error,
)
from app.core.permissions import Permission
from app.db.session import get_db
from app.models.health import (
    EncounterStatus,
    EncounterType,
    HealthDiagnosis,
    HealthEncounter,
    MedicationAdministration,
    TreatmentPlan,
    VaccinationAdministration,
    VeterinaryVisit,
)
from app.models.farm_member import FarmRole
from app.models.user import User
from app.schemas.health import (
    AnimalHealthHistoryResponse,
    EncounterCreate,
    EncounterFinalize,
    EncounterRelatedResponse,
    EncounterResponse,
)
from app.services.health import (
    HealthValidationError,
    add_audit_event,
    cattle_for_health_action,
    scoped_record,
    serializable_snapshot,
    validate_active_member,
    validate_event_time,
)


router = APIRouter(prefix=HEALTH_PREFIX)


@router.post(
    "/encounters",
    response_model=EncounterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_encounter(
    farm_id: UUID,
    data: EncounterCreate,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_CREATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if access.membership.role != FarmRole.VETERINARIAN and any(
        (
            data.finalize,
            data.clinical_observations,
            data.professional_name,
            data.responsible_user_id,
            data.follow_up_due_at,
            data.follow_up_notes,
        )
    ):
        raise HTTPException(
            status_code=403,
            detail=(
                "Farm staff may report symptoms, but clinical examination "
                "and follow-up fields require a Veterinarian membership"
            ),
        )
    try:
        animal = cattle_for_health_action(
            db, farm_id=farm_id, cattle_id=data.cattle_id
        )
        validate_event_time(animal, data.occurred_at, field_name="occurred_at")
        validate_active_member(
            db,
            farm_id=farm_id,
            user_id=data.responsible_user_id,
            field_name="responsible_user_id",
        )
    except HealthValidationError as error:
        raise validation_error(error) from None
    now = datetime.now(timezone.utc)
    encounter = HealthEncounter(
        farm_id=farm_id,
        cattle_id=data.cattle_id,
        encounter_type=data.encounter_type,
        status=(
            EncounterStatus.FINALIZED
            if data.finalize
            else EncounterStatus.DRAFT
        ),
        occurred_at=data.occurred_at,
        symptoms=data.symptoms,
        clinical_observations=data.clinical_observations,
        professional_name=data.professional_name,
        responsible_user_id=data.responsible_user_id,
        follow_up_due_at=data.follow_up_due_at,
        follow_up_notes=data.follow_up_notes,
        created_by_id=current_user.id,
        finalized_at=now if data.finalize else None,
    )
    db.add(encounter)
    commit_or_error(
        db,
        conflict_detail="Encounter conflicts with current health data",
        server_detail="Could not create health encounter",
    )
    db.refresh(encounter)
    return encounter


@router.get("/encounters", response_model=list[EncounterResponse])
def list_encounters(
    farm_id: UUID,
    cattle_id: UUID | None = None,
    encounter_type: EncounterType | None = None,
    clinical_status: EncounterStatus | None = Query(
        default=None, alias="status"
    ),
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    if occurred_from and occurred_to and occurred_from > occurred_to:
        raise HTTPException(
            status_code=422,
            detail="occurred_from cannot be after occurred_to",
        )
    statement = select(HealthEncounter).where(
        HealthEncounter.farm_id == farm_id
    )
    if cattle_id:
        statement = statement.where(HealthEncounter.cattle_id == cattle_id)
    if encounter_type:
        statement = statement.where(
            HealthEncounter.encounter_type == encounter_type
        )
    if clinical_status:
        statement = statement.where(HealthEncounter.status == clinical_status)
    if occurred_from:
        statement = statement.where(
            HealthEncounter.occurred_at >= occurred_from
        )
    if occurred_to:
        statement = statement.where(HealthEncounter.occurred_at <= occurred_to)
    return list(
        db.scalars(
            statement.order_by(
                HealthEncounter.occurred_at.desc(), HealthEncounter.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
    )


@router.get(
    "/encounters/{encounter_id}", response_model=EncounterRelatedResponse
)
def get_encounter(
    farm_id: UUID,
    encounter_id: UUID,
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    encounter = scoped_record(
        db, HealthEncounter, farm_id=farm_id, record_id=encounter_id
    )
    if encounter is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    diagnoses = list(
        db.scalars(
            select(HealthDiagnosis)
            .where(
                HealthDiagnosis.farm_id == farm_id,
                HealthDiagnosis.encounter_id == encounter_id,
            )
            .order_by(HealthDiagnosis.diagnosed_at, HealthDiagnosis.id)
        )
    )
    treatments = list(
        db.scalars(
            select(TreatmentPlan)
            .where(
                TreatmentPlan.farm_id == farm_id,
                TreatmentPlan.encounter_id == encounter_id,
            )
            .order_by(TreatmentPlan.start_date, TreatmentPlan.id)
        )
    )
    return EncounterRelatedResponse(
        encounter=encounter,
        diagnoses=diagnoses,
        treatments=treatments,
    )


@router.post(
    "/encounters/{encounter_id}/finalize",
    response_model=EncounterResponse,
)
def finalize_encounter(
    farm_id: UUID,
    encounter_id: UUID,
    data: EncounterFinalize,
    access: FarmAccess = Depends(
        require_veterinarian_permission(Permission.HEALTH_CREATE)
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    encounter = scoped_record(
        db,
        HealthEncounter,
        farm_id=farm_id,
        record_id=encounter_id,
        lock=True,
    )
    if encounter is None:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if encounter.status != EncounterStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Encounter is already finalized")
    previous = serializable_snapshot(encounter)
    encounter.status = EncounterStatus.FINALIZED
    encounter.finalized_at = datetime.now(timezone.utc)
    add_audit_event(
        db,
        farm_id=farm_id,
        cattle_id=encounter.cattle_id,
        record_type="ENCOUNTER",
        record_id=encounter.id,
        action="FINALIZED",
        reason=data.reason or "Clinical encounter finalized",
        actor_id=current_user.id,
        previous_data=previous,
    )
    commit_or_error(
        db,
        conflict_detail="Encounter could not be finalized",
        server_detail="Could not finalize encounter",
    )
    db.refresh(encounter)
    return encounter


@router.get(
    "/cattle/{cattle_id}/history",
    response_model=AnimalHealthHistoryResponse,
)
def animal_health_history(
    farm_id: UUID,
    cattle_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    access: FarmAccess = Depends(
        require_farm_permission(Permission.HEALTH_VIEW)
    ),
    db: Session = Depends(get_db),
):
    # History remains readable for cattle in any lifecycle state.
    from app.models.cattle import Cattle

    animal = db.scalar(
        select(Cattle.id).where(
            Cattle.id == cattle_id, Cattle.farm_id == farm_id
        )
    )
    if animal is None:
        raise HTTPException(status_code=404, detail="Cattle not found")

    def history(model, order):
        return list(
            db.scalars(
                select(model)
                .where(model.farm_id == farm_id, model.cattle_id == cattle_id)
                .order_by(order.desc(), model.id.desc())
                .limit(limit)
            )
        )

    return AnimalHealthHistoryResponse(
        encounters=history(HealthEncounter, HealthEncounter.occurred_at),
        diagnoses=history(HealthDiagnosis, HealthDiagnosis.diagnosed_at),
        vaccination_administrations=history(
            VaccinationAdministration,
            VaccinationAdministration.administered_at,
        ),
        medication_administrations=history(
            MedicationAdministration, MedicationAdministration.administered_at
        ),
        veterinary_visits=history(VeterinaryVisit, VeterinaryVisit.requested_at),
    )
