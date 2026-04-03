"""Celery configuration for PhishTrack background tasks."""
from datetime import timedelta

from celery import Celery, shared_task
from celery.schedules import crontab

from app.config import settings

# Create Celery app
celery_app = Celery(
    "phishtrack",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.osint",
        "app.tasks.email",
        "app.tasks.monitor",
        "app.tasks.evidence",
        "app.tasks.reports",
        "app.tasks.http_status",
        "app.workers.certstream_worker",
        "app.workers.cleanup",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_TIME_LIMIT - 60,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_send_sent_event=True,
    # Result settings
    result_extended=True,
    result_expires=timedelta(hours=24).total_seconds(),
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    # Rate limiting
    task_default_rate_limit="10/m",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Routing
    task_default_queue="phishtrack",
    task_default_exchange="phishtrack",
    task_default_routing_key="phishtrack",
)

# Beat schedule for periodic monitoring
celery_app.conf.beat_schedule = {
    "check-due-monitoring-tasks": {
        "task": "monitor.check_due",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "check-all-http-status": {
        "task": "http_status.check_all",
        "schedule": crontab(minute="0", hour="*/2"),  # Every 2 hours
    },
    "cleanup-old-results": {
        "task": "monitor.cleanup",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM UTC
    },
    "cleanup-old-detected-domains": {
        "task": "cleanup.detected_domains",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM UTC
    },
    "cleanup-raw-logs-hourly": {
        "task": "cleanup.raw_logs",
        "schedule": crontab(minute=0),  # Every hour
    },
}

# Task queues for different types of work
celery_app.conf.task_queues = {
    "phishtrack": {
        "exchange": "phishtrack",
        "binding_key": "phishtrack",
    },
    "phishtrack.osint": {
        "exchange": "phishtrack.osint",
        "routing_key": "osint",
    },
    "phishtrack.email": {
        "exchange": "phishtrack.email",
        "routing_key": "email",
    },
    "phishtrack.monitor": {
        "exchange": "phishtrack.monitor",
        "routing_key": "monitor",
    },
    "phishtrack.evidence": {
        "exchange": "phishtrack.evidence",
        "routing_key": "evidence",
    },
    "phishtrack.hunting": {
        "exchange": "phishtrack.hunting",
        "routing_key": "hunting",
    },
}

# Task routing
celery_app.conf.task_routes = {
    "app.tasks.osint.*": {"queue": "phishtrack.osint"},
    "app.tasks.email.*": {"queue": "phishtrack.email"},
    "app.tasks.monitor.*": {"queue": "phishtrack.monitor"},
    "app.tasks.evidence.*": {"queue": "phishtrack.evidence"},
    "app.workers.certstream_worker.*": {"queue": "phishtrack.hunting"},
    "app.workers.cleanup.*": {"queue": "phishtrack.hunting"},
    "certstream.*": {"queue": "phishtrack.hunting"},
    "ctlog.*": {"queue": "phishtrack.hunting"},
    "cleanup.*": {"queue": "phishtrack.hunting"},
}


@shared_task(name="health.check")
def health_check() -> dict:
    """Health check task for Celery."""
    return {
        "status": "healthy",
        "message": "Celery worker is running",
    }


# Export shared_task decorator for use in other modules
__all__ = ["celery_app", "shared_task", "health_check"]
