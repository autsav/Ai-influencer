"""Pydantic v2 schemas for the API v1 layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING = "PENDING"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class ContentType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    CAROUSEL = "carousel"


# ── Request schemas ──────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    """POST /api/v1/generations — create a generation job."""
    prompt_seed: str = Field(..., min_length=1, max_length=2000, description="Scene description")
    pillar: str = Field("ai_workflows", description="Content pillar")
    wardrobe: Optional[str] = Field(None, description="Outfit description override")
    mood: Optional[str] = Field(None, description="Mood override")
    style_override: Optional[str] = Field(None, description="Style hint")
    aspect_ratio: str = Field("4:5", description="Aspect ratio: 4:5, 1:1, 16:9, 9:16")
    content_type: ContentType = Field(ContentType.IMAGE, description="Type of content to generate")
    generate_caption: bool = Field(True, description="Also generate a caption via LLM")
    cta_kind: str = Field("none", description="CTA type: save, share, comment, none")
    hashtags: Optional[list[str]] = Field(None, description="Hashtags to append")
    seed: Optional[int] = Field(None, description="Reproducibility seed")
    priority: int = Field(0, ge=0, le=10, description="Priority (0=normal, 10=urgent)")


class JobQuery(BaseModel):
    """GET /api/v1/jobs/{job_id} — query job status."""
    job_id: str


# ── Response schemas ─────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    """Returned when a job is created or queried."""
    job_id: str
    status: JobStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    result_url: Optional[str] = Field(None, description="S3 URL of generated output")
    caption: Optional[str] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100, description="Progress percentage")
    identity_score: Optional[float] = Field(None, description="Face identity cosine similarity")
    passes_gate: Optional[bool] = Field(None, description="Whether face gate passed")
    detail_pass_applied: Optional[bool] = Field(None, description="Whether Pass 2 face detailer ran")


class HealthResponse(BaseModel):
    status: str
    scheduler_running: bool
    bot_running: bool
    celery_running: bool
    redis_connected: bool


class PresignedUploadResponse(BaseModel):
    """POST /api/v1/uploads/presign — get a presigned S3 URL for direct upload."""
    upload_url: str
    object_key: str
    expires_in: int = Field(3600, description="URL validity in seconds")


class InfluencerProfileResponse(BaseModel):
    """GET /api/v1/influencers/{name} — fetch a persona profile."""
    name: str
    version: str
    niche: str
    bio: str
    visual_dna: dict
    content_mix: dict
    lora_url: str
    lora_scale: float