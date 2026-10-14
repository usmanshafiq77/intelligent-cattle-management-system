from fastapi import APIRouter

from app.api.v1.cattle import breeds, lifecycle, media, profiles, weights


breed_router = breeds.router
cattle_router = APIRouter(
    tags=["Cattle Management"]
)
cattle_router.include_router(profiles.router)
cattle_router.include_router(lifecycle.router)
cattle_router.include_router(weights.router)
cattle_router.include_router(media.router)
