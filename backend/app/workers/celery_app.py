from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

__all__ = ["celery_app"]


celery_app: Celery = Celery(
    "once",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.tasks.submission_tasks",
        "app.workers.tasks.renewal_tasks",
        "app.workers.tasks.sanctions_tasks",
        "app.workers.tasks.smoke_test_tasks",
        "app.workers.tasks.audit_tasks",
        "app.workers.tasks.key_rotation_tasks",
        # --- L3.7 imports ---
        "app.workers.tasks.import_tasks",
        # --- /L3.7 imports ---
        # --- L3.8 pdf extraction ---
        "app.workers.tasks.extraction_tasks",
        # --- /L3.8 pdf extraction ---
        # --- L3.9 inbound email ---
        "app.workers.tasks.inbound_tasks",
        # --- /L3.9 inbound email ---
    ],
)


celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_default_retry_delay=60,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    result_expires=60 * 60 * 24 * 7,
)


celery_app.conf.beat_schedule = {
    "sanctions-refresh-ofac-every-6h": {
        "task": "sanctions.refresh_ofac",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"expires": 60 * 60},
    },
    "renewals-scan-expiring-cois-daily": {
        "task": "renewals.scan_expiring_cois",
        "schedule": crontab(minute=0, hour=14),
        "options": {"expires": 60 * 60 * 6},
    },
    "smoke-test-run-all-every-15-min": {
        "task": "smoke_test.run_all",
        "schedule": crontab(minute="*/15"),
        "options": {"expires": 60 * 10},
    },
    "audit-verify-nightly-hash-daily-0200-utc": {
        "task": "audit.verify_nightly_hash",
        "schedule": crontab(minute=0, hour=2),
        "options": {"expires": 60 * 60 * 6},
    },
    "keys-rotate-signing-key-weekly-sun-0400-utc": {
        "task": "keys.rotate_signing_key",
        "schedule": crontab(minute=0, hour=4, day_of_week="sun"),
        "options": {"expires": 60 * 60 * 6},
    },
    "keys-warn-jwt-secret-age-daily-0300-utc": {
        "task": "keys.warn_jwt_secret_age",
        "schedule": crontab(minute=0, hour=3),
        "options": {"expires": 60 * 60 * 6},
    },
    "keys-warn-db-password-age-daily-0315-utc": {
        "task": "keys.warn_db_password_age",
        "schedule": crontab(minute=15, hour=3),
        "options": {"expires": 60 * 60 * 6},
    },
    # --- L3.9 inbound email ---
    "inbound-imap-poll-every-minute": {
        "task": "inbound.imap_poll",
        "schedule": crontab(minute="*"),
        "options": {"expires": 60},
    },
    # --- /L3.9 inbound email ---
}
