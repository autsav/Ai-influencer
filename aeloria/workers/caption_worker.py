"""Celery worker: caption generation via LLM router (MiniMax primary)."""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from aeloria.config import get_settings
from aeloria.generation.caption import write_caption, CaptionError
from aeloria.persona.loader import load_persona

log = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="aeloria.workers.caption_worker.generate_caption_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=2,
)
def generate_caption_task(self, brief: dict[str, Any], cta_kind: str = "none",
                          hashtags: list[str] | None = None) -> dict:
    """
    Generate an Instagram caption via MiniMax LLM.

    Returns:
        Dict with caption text.
    """
    try:
        persona = load_persona()
        settings = get_settings()
        distribution_plan = {"hashtags": hashtags} if hashtags else None
        caption = write_caption(persona, brief, settings=settings,
                                 distribution_plan=distribution_plan, cta_kind=cta_kind)
        log.info("Caption task %s: generated %d chars", self.request.id, len(caption))
        return {"caption": caption}
    except CaptionError as exc:
        log.error("Caption task %s failed: %s", self.request.id, exc)
        raise