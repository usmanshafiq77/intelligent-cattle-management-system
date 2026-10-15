
from fastapi import APIRouter

from app.api.v1.milk import (
    analytics,
    corrections,
    lactations,
    quality,
    sessions,
)


router = APIRouter(tags=["Milk Production Management"])

router.include_router(lactations.router)
router.include_router(sessions.router)
router.include_router(quality.router)
router.include_router(corrections.router)
router.include_router(analytics.router)
