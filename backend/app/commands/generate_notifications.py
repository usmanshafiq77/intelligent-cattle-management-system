"""Run one idempotent notification generation cycle.

Production must invoke this command from a separately supervised scheduler.
It creates in-app records only; email and push delivery are intentionally absent.
"""
import logging

from app.core.logging import configure_logging
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.work_reminders import generate_all_notifications


def main() -> int:
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)
    logger = logging.getLogger(__name__)
    try:
        with SessionLocal() as db:
            created = generate_all_notifications(db)
    except Exception:
        logger.exception("Notification generation cycle failed")
        return 1
    logger.info("Notification generation cycle completed", extra={"created": created})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
