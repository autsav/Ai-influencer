"""FastAPI TestClient tests for the retention endpoint."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _post(post_id, reach, impressions):
    return {
        "post_id": post_id,
        "reach": reach,
        "impressions": impressions,
        "content_pillar": "auto",
        "hook_type": "question",
    }


def test_endpoint_returns_200_and_payload(tmp_path: Path, monkeypatch):
    from aeloria.api.v1.endpoints import retention as ep
    from aeloria.analytics.retention_proxy import retention_report

    data = {
        "posts": [
            _post("P1", 80, 100),
            _post("P2", 20, 100),
        ]
    }
    f = tmp_path / "learnings.json"
    f.write_text(json.dumps(data))
    monkeypatch.setattr(ep, "retention_report", lambda *_a, **_kw: retention_report(f))

    app = FastAPI()
    app.include_router(ep.router)
    client = TestClient(app)

    resp = client.get("/analytics/retention")
    assert resp.status_code == 200
    body = resp.json()
    assert "aggregate" in body
    assert "per_post" in body
    assert "source" in body
    assert body["aggregate"]["counts"]["strong_hook"] == 1
    assert body["aggregate"]["counts"]["weak_hook"] == 1


def test_endpoint_via_main_router_path():
    """Confirm the endpoint is mounted under /api/v1 via the real router."""
    from aeloria.api.v1.router import api_router

    app = FastAPI()
    app.include_router(api_router, prefix="")
    with TestClient(app) as c:
        resp = c.get("/api/v1/analytics/retention")
        assert resp.status_code == 200
        body = resp.json()
        assert "aggregate" in body
        assert "per_post" in body
