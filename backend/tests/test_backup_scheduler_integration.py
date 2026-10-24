import uuid
from datetime import datetime, time, timezone

import pytest
from sqlalchemy import func, select, text

from app.models.settings_backup import BackupConfiguration, BackupJob
from app.models.work_management import AppNotification
from app.services.backup_orchestrator import BACKUP_LOCK, enqueue_scheduled_backup, process_next_backup
from tests.helpers import create_user


pytestmark = pytest.mark.integration


def test_scheduler_is_daily_idempotent_and_marks_sunday_weekly(db_session):
    config = BackupConfiguration(id=1, schedule_enabled=True, daily_time=time(2, 0), timezone="Asia/Karachi", keep_daily=7, keep_weekly=4, include_media=False)
    db_session.add(config); db_session.commit()
    now = datetime(2026, 10, 25, 3, 0, tzinfo=timezone.utc)
    first = enqueue_scheduled_backup(db_session, now=now)
    second = enqueue_scheduled_backup(db_session, now=now)
    assert first.id == second.id
    assert first.backup_type == "WEEKLY"
    assert db_session.scalar(select(func.count()).select_from(BackupJob).where(BackupJob.request_id == first.request_id)) == 1


def test_session_advisory_lock_blocks_another_connection(db_session, pg_engine):
    assert db_session.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": BACKUP_LOCK}) is True
    try:
        with pg_engine.connect() as other:
            assert other.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": BACKUP_LOCK}) is False
    finally:
        assert db_session.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": BACKUP_LOCK}) is True


def test_final_worker_failure_is_persisted_and_alerts_system_admin(db_session):
    admin = create_user(db_session, email="backup-alert-admin@example.com"); admin.is_system_admin = True
    job = BackupJob(request_id=uuid.uuid4(), backup_type="ON_DEMAND", status="PENDING", requested_by_id=admin.id, max_attempts=1)
    db_session.add(job); db_session.commit()
    result = process_next_backup(db_session)
    assert result.id == job.id and result.status == "FAILED" and result.attempt_count == 1
    alert = db_session.scalar(select(AppNotification).where(AppNotification.user_id == admin.id, AppNotification.source_id == job.id))
    assert alert is not None and alert.route == "/admin/backups/alerts"
    assert "key" not in alert.message.lower() and "password" not in alert.message.lower()
