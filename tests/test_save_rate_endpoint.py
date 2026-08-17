"""FastAPI TestClient test for the save-rate endpoint."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _post(saves, impressions, pillar="auto", hook="question"):
    return {
        "post_id": f"P{saves}{impressions}",
        "content_pillar": pillar,
        "hook_type": hook,
        "saves": saves,
        "impressions": impressions,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def test_endpoint_returns_200_and_payload(tmp_path: Path, monkeypatch):
    from aeloria.api.v1.endpoints import save_rate as ep
    from aeloria.analytics.save_rate import save_rate_report

    data = {"posts": [_post(20, 100), _post(10, 100, pillar="tools")]}
    f = tmp_path / "learnings.json"
    f.write_text(json.dumps(data))
    monkeypatch.setattr(ep, "save_rate_report", lambda *_a, **_kw: save_rate_report(f))

    app = FastAPI()
    app.include_router(ep.router)
    client = TestClient(app)

    resp = client.get("/analytics/save-rate")
    assert resp.status_code == 200
    body = resp.json()
    assert "per_pillar" in body
    assert "per_hook_type" in body
    assert "rolling_7d" in body
    assert "top_posts" in body
    assert "post_count" in body
    assert body["post_count"] == 2
    assert "auto" in body["per_pillar"]
    assert body["per_pillar"]["auto"] == 0.2


def test_endpoint_via_main_router_path():
    """Confirm the endpoint is mounted under /api/v1 via the real router."""
    from aeloria.api.v1.router import api_router

    app = FastAPI()
    app.include_router(api_router, prefix="")
    with TestClient(app) as c:
        resp = c.get("/api/v1/analytics/save-rate")
        assert resp.status_code == 200
        assert "per_pillar" in resp.json()