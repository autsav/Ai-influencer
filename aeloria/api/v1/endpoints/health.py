"""Health endpoint — GET /api/v1/health."""
from __future__ import annotations

import logging

from fastapi import APIRouter

from aeloria.schemas.v1 import HealthResponse
from aeloria.core.celery_app import celery_app

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
async def health():
    """Check system health including Celery/Redis connectivity."""
    redis_ok = False
    celery_ok = False
    try:
        conn = celery_app.connection()
        conn.ensure_connection(max_retries=1, timeout=2)
        redis_ok = True
        celery_ok = True
        conn.close()
    except Exception as exc:
        log.debug("Health check: Celery/Redis not reachable: %s", exc)

    return HealthResponse(
        status="ok" if redis_ok else "degraded",
        scheduler_running=False,  # set by app lifespan
        bot_running=False,
        celery_running=celery_ok,
        redis_connected=redis_ok,
    )