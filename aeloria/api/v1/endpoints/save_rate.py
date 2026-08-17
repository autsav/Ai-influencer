"""GET /api/v1/analytics/save-rate — returns the save_rate_report dict as JSON."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from aeloria.analytics.save_rate import save_rate_report

router = APIRouter()


@router.get("/analytics/save-rate")
def get_save_rate() -> dict:
    return save_rate_report(Path("aeloria/distribution/learnings.json"))