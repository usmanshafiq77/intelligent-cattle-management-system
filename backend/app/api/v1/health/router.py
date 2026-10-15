from fastapi import APIRouter

from app.api.v1.health import (
    diagnoses,
    encounters,
    reminders,
    treatments,
    vaccinations,
    vet_visits,
)


router = APIRouter(tags=["Health and Veterinary Management"])
router.include_router(encounters.router)
router.include_router(diagnoses.router)
router.include_router(vaccinations.router)
router.include_router(treatments.router)
router.include_router(vet_visits.router)
router.include_router(reminders.router)
