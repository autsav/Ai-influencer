"""Celery worker: image generation via fal.ai FLUX.1 + LoRA.

This runs in a separate process from the FastAPI app — never blocks HTTP requests.
Exponential backoff retries on transient failures.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from celery.exceptions import Retry

from aeloria.config import get_settings
from aeloria.generation.fal_images import generate_image, ImageResult
from aeloria.generation.prompt_builder import build_prompt
from aeloria.persona.loader import load_persona
from aeloria.storage.r2 import R2

log = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="aeloria.workers.image_worker.generate_image_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def generate_image_task(self, brief: dict[str, Any]) -> dict:
    """
    Build prompt from brief → generate image via fal.ai → upload to S3.

    Args:
        brief: Generation brief dict with prompt_seed, pillar, wardrobe, etc.

    Returns:
        Dict with s3_url, cost_usd, prompt (for DB record).
    """
    try:
        settings = get_settings()
        persona = load_persona()
        prompt = build_prompt(persona, brief)

        log.info("Image task %s: generating (seed=%s)", self.request.id, brief.get("seed"))
        result: ImageResult = generate_image(prompt, settings)

        # Upload to R2/S3
        r2 = R2(settings)
        object_key = f"generations/{self.request.id}.png"
        r2.put_bytes(object_key, result.image_bytes, content_type="image/png")
        s3_url = r2.public_url(object_key)

        log.info("Image task %s: uploaded to %s, cost=$%.4f", self.request.id, s3_url, result.cost_usd)

        return {
            "s3_url": s3_url,
            "cost_usd": result.cost_usd,
            "prompt": prompt,
            "object_key": object_key,
        }

    except Exception as exc:
        log.error("Image task %s failed: %s", self.request.id, exc)
        raise Retry(exc=exc) if self.request.retries < self.max_retries else exc