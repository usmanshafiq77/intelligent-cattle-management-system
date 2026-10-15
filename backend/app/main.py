import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.v1.farms import router as farms_router
from app.api.v1.invitations import router as invitations_router
from app.api.v1.roles import router as roles_router
from app.api.v1.staff import router as staff_router
from app.api.v1.cattle import breed_router, cattle_router
from app.api.v1.health import router as health_router
from app.api.v1.milk import router as milk_router

from app.db.session import engine
from app.api.v1.auth import router as auth_router


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Intelligent Cattle Management System API",
    description="Backend API for the ICMS mobile and web application.",
    version="0.1.0",
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(farms_router, prefix="/api/v1")
app.include_router(invitations_router, prefix="/api/v1")
app.include_router(staff_router, prefix="/api/v1")
app.include_router(roles_router, prefix="/api/v1")
app.include_router(breed_router, prefix="/api/v1")
app.include_router(cattle_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(milk_router, prefix="/api/v1")

@app.get("/", tags=["General"])
def root():
    return {
        "message": "Welcome to the ICMS API",
        "version": "0.1.0",
    }


@app.get("/api/v1/health", tags=["System"])
def health_check():
    return {
        "status": "ok",
        "service": "ICMS Backend",
    }


@app.get("/api/v1/health/db", tags=["System"])
def database_health_check():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable",
        ) from None

    return {
        "status": "ok",
        "database": "connected",
    }
