"""Core configuration for the Celery + Redis async task infrastructure."""
from __future__ import annotations

import os

# Redis is used as both the Celery broker and the result backend.
# In production, set REDIS_URL env var. Default assumes local Redis.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Celery config
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = "Europe/London"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 min hard limit per task
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 min soft limit → SoftTimeLimitExceeded
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # fair scheduling for long tasks
CELERY_WORKER_MAX_RETRIES = 3

# Task routing — separate queues for image gen (GPU-heavy) vs light tasks
CELERY_TASK_ROUTES = {
    "aeloria.workers.image_worker.generate_image_task": {"queue": "image"},
    "aeloria.workers.video_worker.generate_video_task": {"queue": "video"},
    "aeloria.workers.caption_worker.generate_caption_task": {"queue": "light"},
    "aeloria.workers.upscale_worker.upscale_image_task": {"queue": "image"},
}