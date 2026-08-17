"""GET /api/v1/analytics/retention — retention proxy from IG Insights reach/impressions gap."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from aeloria.analytics.retention_proxy import retention_report

router = APIRouter()


@router.get("/analytics/retention")
def get_retention() -> dict:
    return retention_report(Path("aeloria/distribution/learnings.json"))
