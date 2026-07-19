from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "forgeboard",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks",
        "app.workers.scheduler",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Scheduler polling — runs every minute to check for due scheduled agents
    beat_schedule={
        "sync-scheduled-agents": {
            "task": "sync_scheduled_agents",
            "schedule": 60.0,  # every 60 seconds
        },
    },
    # Worker settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,  # one task at a time per worker slot for fairness
)
