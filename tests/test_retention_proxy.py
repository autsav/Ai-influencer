"""Unit tests for aeloria.analytics.retention_proxy — all 4 public functions."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeloria.analytics import retention_proxy as rp


# --- retention_score ---

def test_retention_score_basic_ratio():
    assert rp.retention_score(70, 100) == pytest.approx(0.7)


def test_retention_score_clamped_high():
    assert rp.retention_score(150, 100) == pytest.approx(1.0)


def test_retention_score_clamped_low():
    assert rp.retention_score(-10, 100) == pytest.approx(0.0)


def test_retention_score_zero_impressions():
    assert rp.retention_score(100, 0) == 0.0


def test_retention_score_negative_impressions():
    assert rp.retention_score(50, -5) == 0.0


# --- classify_hook_performance ---

def test_classify_strong_hook():
    assert rp.classify_hook_performance(80, 100) == "strong_hook"


def test_classify_weak_hook():
    assert rp.classify_hook_performance(20, 100) == "weak_hook"


def test_classify_normal():
    assert rp.classify_hook_performance(50, 100) == "normal"


def test_classify_zero_impressions_is_normal():
    # Zero impressions → score 0.0 → weak_hook (≤0.30)
    assert rp.classify_hook_performance(0, 0) == "weak_hook"


# --- aggregate_hook_performance ---

def test_aggregate_buckets_posts():
    posts = [
        {"post_id": "A", "reach": 80, "impressions": 100},  # strong
        {"post_id": "B", "reach": 20, "impressions": 100},  # weak
        {"post_id": "C", "reach": 50, "impressions": 100},  # normal
        {"post_id": "D", "reach": 0, "impressions": 0},    # skipped: impressions=0
        {"post_id": "E"},                                  # missing fields → skipped
    ]
    out = rp.aggregate_hook_performance(posts)
    assert out["counts"]["strong_hook"] == 1
    assert out["counts"]["weak_hook"] == 1
    assert out["counts"]["normal"] == 1
    assert out["total_posts"] == 5
    assert out["scored_posts"] == 3  # A/B/C; D skipped (impressions<=0); E skipped (missing)
    # avg of: 0.8, 0.2, 0.5 = 0.5
    assert out["avg_retention_score"] == pytest.approx(0.5, abs=0.001)


def test_aggregate_empty_input():
    out = rp.aggregate_hook_performance([])
    assert out["counts"] == {"strong_hook": 0, "weak_hook": 0, "normal": 0}
    assert out["avg_retention_score"] == 0.0
    assert out["total_posts"] == 0
    assert out["scored_posts"] == 0


def test_aggregate_shares_sum_to_one():
    posts = [
        {"post_id": "A", "reach": 80, "impressions": 100},
        {"post_id": "B", "reach": 20, "impressions": 100},
    ]
    out = rp.aggregate_hook_performance(posts)
    share_sum = sum(out["shares"].values())
    assert share_sum == pytest.approx(1.0)


# --- retention_report ---

def test_retention_report_reads_learnings(tmp_path: Path):
    data = {
        "posts": [
            {"post_id": "P1", "reach": 80, "impressions": 100},
            {"post_id": "P2", "reach": 20, "impressions": 100},
            {"post_id": "P3", "reach": 50, "impressions": 100},
        ]
    }
    f = tmp_path / "learnings.json"
    f.write_text(json.dumps(data))

    out = rp.retention_report(f)
    assert out["source"] == str(f)
    assert out["aggregate"]["counts"]["strong_hook"] == 1
    assert out["aggregate"]["counts"]["weak_hook"] == 1
    assert out["aggregate"]["counts"]["normal"] == 1
    assert len(out["per_post"]) == 3
    assert {p["classification"] for p in out["per_post"]} == {
        "strong_hook", "weak_hook", "normal"
    }


def test_retention_report_missing_file(tmp_path: Path):
    f = tmp_path / "does_not_exist.json"
    out = rp.retention_report(f)
    assert out["source"] == "missing"
    assert out["per_post"] == []
    assert out["aggregate"]["total_posts"] == 0


def test_retention_report_malformed_json(tmp_path: Path):
    f = tmp_path / "bad.json"
    f.write_text("{not valid json")
    out = rp.retention_report(f)
    assert out["source"] == "missing"


def test_retention_report_no_posts_field(tmp_path: Path):
    f = tmp_path / "nooposts.json"
    f.write_text(json.dumps({"other": "data"}))
    out = rp.retention_report(f)
    assert out["per_post"] == []
    assert out["aggregate"]["total_posts"] == 0
