import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.api.v1.farms import router as farms_router
from app.api.v1.invitations import router as invitations_router
from app.api.v1.roles import router as roles_router
from app.api.v1.staff import router as staff_router
from app.api.v1.cattle import breed_router, cattle_router
from app.api.v1.health import router as health_router
from app.api.v1.milk import router as milk_router
from app.api.v1.feed import router as feed_router
from app.api.v1.breeding import router as breeding_router
from app.api.v1.finance import router as finance_router
from app.api.v1.marketplace import router as marketplace_router

from app.db.session import engine
from app.api.v1.auth import router as auth_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.migrations import (
    EXPECTED_DATABASE_REVISION,
    current_database_revision,
)


settings = get_settings()
configure_logging(level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Intelligent Cattle Management System API",
    description="Backend API for the ICMS mobile and web application.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
)


@app.middleware("http")
async def security_and_request_logging(request: Request, call_next):
    request_id = uuid.uuid4().hex
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Request-ID"] = request_id
    if request.url.path.startswith("/api/v1/auth"):
        response.headers["Cache-Control"] = "no-store"
    if settings.APP_ENV.strip().lower() == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    logger.info(
        "request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response
app.include_router(auth_router, prefix="/api/v1")
app.include_router(farms_router, prefix="/api/v1")
app.include_router(invitations_router, prefix="/api/v1")
app.include_router(staff_router, prefix="/api/v1")
app.include_router(roles_router, prefix="/api/v1")
app.include_router(breed_router, prefix="/api/v1")
app.include_router(cattle_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(milk_router, prefix="/api/v1")
app.include_router(feed_router, prefix="/api/v1")
app.include_router(breeding_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")

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
            revision = current_database_revision(connection)
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable",
        ) from None

    if revision != EXPECTED_DATABASE_REVISION:
        logger.error(
            "Database migration revision mismatch: expected=%s actual=%s",
            EXPECTED_DATABASE_REVISION,
            revision or "missing",
        )
        raise HTTPException(
            status_code=503,
            detail="Database migration required",
        )

    return {
        "status": "ok",
        "database": "connected",
        "migration_revision": revision,
    }
