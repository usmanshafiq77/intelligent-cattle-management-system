import logging

from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import engine


logger = logging.getLogger(__name__)

app = FastAPI(
    title="Intelligent Cattle Management System API",
    description="Backend API for the ICMS mobile and web application.",
    version="0.1.0",
)


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