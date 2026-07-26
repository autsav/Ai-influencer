"""Celery worker: image upscaling via Vellum AI."""
from __future__ import annotations

import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="aeloria.workers.upscale_worker.upscale_image_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
)
def upscale_image_task(self, image_url: str) -> dict:
    """
    Upscale an image via Vellum AI and upload the result to S3.

    Returns:
        Dict with s3_url of the upscaled image.
    """
    from aeloria.config import get_settings
    from aeloria.generation.vellum_upscaler import VellumUpscaler
    from aeloria.storage.r2 import R2
    import httpx

    try:
        settings = get_settings()
        # Download the source image
        resp = httpx.get(image_url, timeout=30)
        resp.raise_for_status()
        source_bytes = resp.content

        # Upscale
        upscaler = VellumUpscaler(settings)
        upscaled_bytes = upscaler.upscale(source_bytes)

        # Upload
        r2 = R2(settings)
        object_key = f"upscaled/{self.request.id}.png"
        r2.put_bytes(object_key, upscaled_bytes, content_type="image/png")
        s3_url = r2.public_url(object_key)
        log.info("Upscale task %s: uploaded to %s", self.request.id, s3_url)
        return {"s3_url": s3_url, "object_key": object_key}
    except Exception as exc:
        log.error("Upscale task %s failed: %s", self.request.id, exc)
        raise