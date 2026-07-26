"""POST /api/v1/generations — create a generation job (non-blocking)."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from aeloria.config import get_settings, Settings
from aeloria.schemas.v1 import GenerateRequest, JobResponse
from aeloria.workers.image_worker import generate_image_task
from aeloria.workers.caption_worker import generate_caption_task

router = APIRouter()
log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


def _auth(creds: HTTPAuthorizationCredentials | None = Security(_bearer),
          settings: Settings = Depends(get_settings)) -> bool:
    import secrets
    if not settings.api_secret_key:
        return True  # auth disabled in dev
    if creds is None:
        raise HTTPException(401, "unauthorized")
    if not secrets.compare_digest(creds.credentials, settings.api_secret_key):
        raise HTTPException(401, "unauthorized")
    return True


@router.post("/generations", response_model=JobResponse, status_code=202)
async def create_generation(req: GenerateRequest, _authed: bool = Depends(_auth)):
    """
    Enqueue a generation job. Returns immediately with job_id + PENDING status.
    The Celery worker handles image generation + caption in the background.
    """
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    brief = {
        "prompt_seed": req.prompt_seed,
        "pillar": req.pillar,
        "wardrobe": req.wardrobe,
        "mood": req.mood,
        "style_override": req.style_override,
        "seed": req.seed,
        "id": job_id,
    }

    # Enqueue the image generation task
    image_chain = generate_image_task.apply_async(
        args=[brief],
        task_id=job_id,
        queue="image",
    )
    log.info("Enqueued image task %s for job %s", image_chain.id, job_id)

    # Optionally chain a caption task after image generation
    if req.generate_caption:
        generate_caption_task.apply_async(
            args=[brief, req.cta_kind, req.hashtags],
            task_id=f"{job_id}-caption",
            queue="light",
        )

    return JobResponse(
        job_id=job_id,
        status="PENDING",
        created_at=now,
        updated_at=now,
    )