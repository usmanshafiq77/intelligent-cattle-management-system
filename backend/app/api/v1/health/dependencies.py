import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.health import HealthValidationError


logger = logging.getLogger(__name__)
HEALTH_PREFIX = "/farms/{farm_id}/health"


def validation_error(error: HealthValidationError | ValueError) -> HTTPException:
    message = str(error)
    code = status.HTTP_404_NOT_FOUND if message.endswith("not found") else 422
    return HTTPException(status_code=code, detail=message)


def constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)


def commit_or_error(
    db: Session,
    *,
    conflict_detail: str,
    server_detail: str,
) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_detail) from None
    except SQLAlchemyError:
        db.rollback()
        logger.exception(server_detail)
        raise HTTPException(status_code=500, detail=server_detail) from None


def ensure_same_farm(value: UUID, farm_id: UUID) -> None:
    if value != farm_id:
        raise HTTPException(status_code=404, detail="Health record not found")
