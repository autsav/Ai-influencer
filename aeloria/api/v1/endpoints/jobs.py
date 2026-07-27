"""GET /api/v1/jobs/{job_id} — query job status. SSE stream endpoint for live updates."""
from __future__ import annotations

import asyncio
import logging

from celery.result import AsyncResult
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from aeloria.schemas.v1 import ConsistencyMetrics, JobResponse, JobStatus
from aeloria.core.celery_app import celery_app

router = APIRouter()
log = logging.getLogger(__name__)


def _celery_result_to_response(job_id: str) -> JobResponse:
    """Map Celery AsyncResult to a JobResponse."""
    result = AsyncResult(job_id, app=celery_app)
    state = result.state

    status_map = {
        "PENDING": JobStatus.PENDING,
        "STARTED": JobStatus.STARTED,
        "RETRY": JobStatus.RETRYING,
        "FAILURE": JobStatus.FAILED,
        "SUCCESS": JobStatus.COMPLETED,
    }
    job_status = status_map.get(state, JobStatus.PENDING)

    result_url = None
    caption = None
    cost_usd = None
    error = None
    consistency = None

    if state == "SUCCESS" and result.result:
        data = result.result
        result_url = data.get("s3_url")
        cost_usd = data.get("cost_usd")
        # Two-pass consistency metrics (only present for image/video jobs that ran the pipeline)
        if data.get("identity_score") is not None or data.get("passes_gate") is not None:
            consistency = ConsistencyMetrics(
                identity_score=data.get("identity_score"),
                passes_gate=data.get("passes_gate"),
                detail_pass_applied=data.get("detail_pass_applied"),
                pass1_score=data.get("pass1_score"),
                pass2_score=data.get("pass2_score"),
            )

    if state == "FAILURE" and result.result:
        error = str(result.result)

    # Also check for caption task
    caption_result = AsyncResult(f"{job_id}-caption", app=celery_app)
    if caption_result.state == "SUCCESS" and caption_result.result:
        caption = caption_result.result.get("caption")

    return JobResponse(
        job_id=job_id,
        status=job_status,
        result_url=result_url,
        caption=caption,
        cost_usd=cost_usd,
        error=error,
        consistency=consistency,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get the current status of a job."""
    return _celery_result_to_response(job_id)


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    """Server-Sent Events stream for real-time job status updates."""
    async def event_generator():
        last_status = None
        for _ in range(120):  # max 2 minutes (poll every 1s)
            resp = _celery_result_to_response(job_id)
            if resp.status != last_status:
                last_status = resp.status
                # SSE format
                data = resp.model_dump_json()
                yield f"data: {data}\n\n"
            if resp.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")