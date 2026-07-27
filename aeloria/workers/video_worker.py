"""Celery worker: video generation via Kling/Wan API."""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="aeloria.workers.video_worker.generate_video_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=180,
    max_retries=2,
)
def generate_video_task(self, prompt: str, image_url: str | None = None,
                        duration: int = 5, aspect_ratio: str = "9:16") -> dict:
    """
    Generate a short video via Kling/Wan API from a prompt or source image.
    This is a stub — the actual video generation API call lives in aeloria.generation.video_engine.

    Returns:
        Dict with s3_url of the generated video.
    """
    from aeloria.config import get_settings
    from aeloria.generation.video_engine import generate_video
    from aeloria.storage.r2 import R2

    try:
        settings = get_settings()
        video_bytes = generate_video(prompt, image_url=image_url, duration=duration,
                                      aspect_ratio=aspect_ratio)
        r2 = R2(settings)
        object_key = f"videos/{self.request.id}.mp4"
        r2.put_bytes(object_key, video_bytes, content_type="video/mp4")
        s3_url = r2.public_url(object_key)
        log.info("Video task %s: uploaded to %s", self.request.id, s3_url)
        return {"s3_url": s3_url, "object_key": object_key}
    except Exception as exc:
        log.error("Video task %s failed: %s", self.request.id, exc)
        raise