"""
Celery application for BHOOMI background jobs (PRODUCT SPEC section 41):
weather sync, satellite sync, risk/advisory recomputation, embedding
generation, document ingestion, model evaluation, notification delivery,
and cleanup. Every task is idempotent and retryable with exponential
backoff.
"""
from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "bhoomi",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
    task_time_limit=120,
    beat_schedule={
        "sync-weather-every-30-minutes": {
            "task": "app.workers.tasks.sync_all_farms_weather",
            "schedule": crontab(minute="*/30"),
        },
        "sync-satellite-daily": {
            "task": "app.workers.tasks.sync_all_farms_satellite",
            "schedule": crontab(hour=2, minute=0),
        },
        "cleanup-stale-cache-daily": {
            "task": "app.workers.tasks.cleanup_stale_data",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)
