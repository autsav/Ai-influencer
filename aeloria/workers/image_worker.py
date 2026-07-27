"""Celery worker: image generation with two-pass character consistency.

Pass 1: FLUX.1 + LoRA + PuLID face identity → full image
Pass 2: Face detailer inpainting → fix facial artifacts (conditional)

Uses the consistency pipeline orchestrator for zero-drift identity preservation.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from aeloria.config import get_settings
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
    Run the full two-pass consistency pipeline:
    1. Build prompt from brief + persona
    2. Pass 1: Generate with PuLID + LoRA (or LoRA fallback)
    3. Pass 2: Face detailer refinement (conditional on face size)
    4. Upload to S3/R2
    5. Return result with identity scores

    Args:
        brief: Generation brief dict with prompt_seed, pillar, wardrobe, etc.

    Returns:
        Dict with s3_url, cost_usd, prompt, identity_score, passes_gate.
    """
    try:
        settings = get_settings()

        # Load reference face image for PuLID + face gate
        reference_bytes = None
        import os
        ref_image_path = "aeloria/persona/reference_face.jpg"
        if os.path.exists(ref_image_path):
            with open(ref_image_path, "rb") as f:
                reference_bytes = f.read()
            log.info("Loaded reference face: %s (%d bytes)", ref_image_path, len(reference_bytes))
        else:
            log.warning("No reference face image at %s — PuLID disabled, LoRA-only", ref_image_path)

        # Run the two-pass consistency pipeline
        from aeloria.generation.consistency_pipeline import generate_consistent
        from aeloria.persona.loader import load_persona

        persona = load_persona()
        use_pulid = getattr(settings, "pulid_enabled", True) and reference_bytes is not None

        result = generate_consistent(
            brief=brief,
            persona=persona,
            settings=settings,
            reference_bytes=reference_bytes,
            use_pulid=use_pulid,
            pulid_weight=getattr(settings, "pulid_weight", 0.85),
            face_denoise=getattr(settings, "face_detailer_denoise", 0.28),
            seed=brief.get("seed"),
        )

        # Upload to R2/S3
        r2 = R2(settings)
        object_key = f"generations/{self.request.id}.png"
        r2.put_bytes(object_key, result.image_bytes, content_type="image/png")
        s3_url = r2.public_url(object_key)

        log.info(
            "Image task %s: uploaded to %s, cost=$%.4f, identity=%.4f, passes_gate=%s",
            self.request.id, s3_url, result.cost_usd,
            result.identity_score, result.passes_gate,
        )

        return {
            "s3_url": s3_url,
            "cost_usd": result.cost_usd,
            "identity_score": result.identity_score,
            "passes_gate": result.passes_gate,
            "detail_pass_applied": result.detail_pass_applied,
            "pass1_score": result.pass1_score,
            "pass2_score": result.pass2_score,
            "object_key": object_key,
        }

    except Exception as exc:
        log.error("Image task %s failed: %s", self.request.id, exc)
        raise exc