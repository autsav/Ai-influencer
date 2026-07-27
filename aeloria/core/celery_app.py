"""Celery app instance — shared across all workers and the API layer."""
from __future__ import annotations

from celery import Celery

from aeloria.core.config_celery import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    CELERY_TASK_SERIALIZER,
    CELERY_RESULT_SERIALIZER,
    CELERY_ACCEPT_CONTENT,
    CELERY_TIMEZONE,
    CELERY_TASK_TRACK_STARTED,
    CELERY_TASK_TIME_LIMIT,
    CELERY_TASK_SOFT_TIME_LIMIT,
    CELERY_WORKER_PREFETCH_MULTIPLIER,
    CELERY_WORKER_MAX_RETRIES,
    CELERY_TASK_ROUTES,
)

celery_app = Celery(
    "aeloria",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        "aeloria.workers.image_worker",
        "aeloria.workers.video_worker",
        "aeloria.workers.caption_worker",
        "aeloria.workers.upscale_worker",
    ],
)

celery_app.conf.update(
    task_serializer=CELERY_TASK_SERIALIZER,
    result_serializer=CELERY_RESULT_SERIALIZER,
    accept_content=CELERY_ACCEPT_CONTENT,
    timezone=CELERY_TIMEZONE,
    task_track_started=CELERY_TASK_TRACK_STARTED,
    task_time_limit=CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=CELERY_TASK_SOFT_TIME_LIMIT,
    worker_prefetch_multiplier=CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_acks_late=True,  # re-deliver task if worker crashes
    task_default_queue="default",
    task_routes=CELERY_TASK_ROUTES,
    # Exponential backoff for retries
    task_default_retry_delay=10,
    task_default_max_retries=CELERY_WORKER_MAX_RETRIES,
)