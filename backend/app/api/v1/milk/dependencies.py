import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.services.milk import MilkValidationError


logger = logging.getLogger(__name__)
MILK_PREFIX = "/farms/{farm_id}/milk"


def validation_error(error: MilkValidationError | ValueError) -> HTTPException:
    message = str(error)
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND if message.endswith("not found") else 422,
        detail=message,
    )


def commit_or_error(db: Session, *, conflict_detail: str, server_detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=conflict_detail) from None
    except SQLAlchemyError:
        db.rollback()
        logger.exception(server_detail)
        raise HTTPException(status_code=500, detail=server_detail) from None
