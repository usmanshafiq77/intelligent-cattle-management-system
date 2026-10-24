import logging
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.backup_orchestrator import enqueue_scheduled_backup, process_next_backup

def main():
    settings=get_settings(); configure_logging(level=settings.LOG_LEVEL,log_format=settings.LOG_FORMAT)
    with SessionLocal() as db: enqueue_scheduled_backup(db); job=process_next_backup(db)
    logging.getLogger(__name__).info("Backup worker cycle complete",extra={"backup_job_id":str(job.id) if job else None})
    return 0 if not job or job.status != "FAILED" else 1

if __name__ == "__main__": raise SystemExit(main())
