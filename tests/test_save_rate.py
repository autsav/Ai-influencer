"""Unit tests for aeloria.analytics.save_rate — all 5 public functions."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from aeloria.analytics import save_rate as sr


def _post(saves, impressions, pillar="p", hook="h", recorded_at=None):
    return {
        "post_id": f"P{saves}{impressions}",
        "content_pillar": pillar,
        "hook_type": hook,
        "saves": saves,
        "impressions": impressions,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
    }


def test_save_rate_per_pillar_groups_and_averages():
    posts = [
        _post(10, 100, pillar="automation"),
        _post(20, 100, pillar="automation"),
        _post(5, 100, pillar="tools"),
        _post(0, 0, pillar="tools"),  # impressions=0 → skipped
    ]
    out = sr.save_rate_per_pillar(posts)
    assert out["automation"] == pytest.approx(0.15)
    assert out["tools"] == pytest.approx(0.05)


def test_save_rate_per_pillar_empty_input():
    assert sr.save_rate_per_pillar([]) == {}


def test_save_rate_per_hook_type_groups_and_averages():
    posts = [
        _post(50, 100, hook="question"),
        _post(10, 100, hook="question"),
        _post(40, 100, hook="stat"),
    ]
    out = sr.save_rate_per_hook_type(posts)
    assert out["question"] == pytest.approx(0.30)
    assert out["stat"] == pytest.approx(0.40)


def test_rolling_save_rate_filters_by_window():
    now = datetime.now(timezone.utc)
    recent = _post(30, 100, recorded_at=now.isoformat())
    old = _post(50, 100, recorded_at=(now - timedelta(days=30)).isoformat())
    rate = sr.rolling_save_rate([recent, old], days=7)
    assert rate == pytest.approx(0.30)


def test_rolling_save_rate_returns_zero_when_no_recent_posts():
    now = datetime.now(timezone.utc)
    old = _post(50, 100, recorded_at=(now - timedelta(days=30)).isoformat())
    assert sr.rolling_save_rate([old], days=7) == 0.0


def test_rolling_save_rate_handles_naive_timestamp():
    now = datetime.now(timezone.utc)
    naive = now.replace(tzinfo=None).isoformat()
    p = _post(20, 100, recorded_at=naive)
    assert sr.rolling_save_rate([p], days=7) == pytest.approx(0.20)


def test_top_posts_by_save_rate_sorted_and_truncated():
    posts = [
        _post(1, 100),  # 0.01
        _post(50, 100),  # 0.50
        _post(25, 100),  # 0.25
        _post(0, 100),  # 0.00
    ]
    top = sr.top_posts_by_save_rate(posts, n=2)
    assert len(top) == 2
    assert top[0]["save_rate"] == pytest.approx(0.50)
    assert top[1]["save_rate"] == pytest.approx(0.25)
    assert "save_rate" in top[0]


def test_top_posts_skips_zero_impressions():
    posts = [_post(10, 0), _post(5, 100)]
    top = sr.top_posts_by_save_rate(posts, n=10)
    assert len(top) == 1
    assert top[0]["save_rate"] == pytest.approx(0.05)


def test_save_rate_report_from_file(tmp_path: Path):
    data = {
        "posts": [
            _post(10, 100, pillar="auto", hook="q"),
            _post(20, 100, pillar="auto", hook="q"),
            _post(5, 100, pillar="tools", hook="s"),
        ],
        "best_hooks": [],
    }
    f = tmp_path / "learnings.json"
    f.write_text(json.dumps(data))
    rep = sr.save_rate_report(f)
    assert rep["post_count"] == 3
    assert rep["per_pillar"]["auto"] == pytest.approx(0.15)
    assert rep["per_hook_type"]["q"] == pytest.approx(0.15)
    assert rep["rolling_7d"] == pytest.approx((0.10 + 0.20 + 0.05) / 3)
    assert len(rep["top_posts"]) == 3
    assert rep["source"] == str(f)


def test_save_rate_report_missing_file(tmp_path: Path):
    rep = sr.save_rate_report(tmp_path / "missing.json")
    assert rep["post_count"] == 0
    assert rep["per_pillar"] == {}
    assert rep["top_posts"] == []
    assert rep["rolling_7d"] == 0.0