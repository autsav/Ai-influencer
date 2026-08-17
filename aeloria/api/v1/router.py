"""API v1 router — assembles all endpoint routers under /api/v1."""
from __future__ import annotations

from fastapi import APIRouter

from aeloria.api.v1.endpoints import generations, jobs, newsletter, uploads, influencers, health, save_rate

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(generations.router, tags=["generations"])
api_router.include_router(jobs.router, tags=["jobs"])
api_router.include_router(uploads.router, tags=["uploads"])
api_router.include_router(influencers.router, tags=["influencers"])
api_router.include_router(newsletter.router, tags=["newsletter"])
api_router.include_router(save_rate.router, tags=["analytics"])