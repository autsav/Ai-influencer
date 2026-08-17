"""
Retention proxy from IG Insights — diagnose hook performance.

When `reach < impressions * 0.30`, the post's opening 3s failed (hook problem).
When `reach > impressions * 0.70`, the post's hook worked (good signal).

This is a proxy because true retention curves require authenticated YouTube/IG Studio access.
The reach/impressions gap is the best public-API signal.

Public functions:
- retention_score(reach: int, impressions: int) -> float
  Returns 0.0–1.0 (reach / impressions, clamped).
- classify_hook_performance(reach: int, impressions: int) -> str
  Returns 'strong_hook' / 'weak_hook' / 'normal'.
- aggregate_hook_performance(posts: list[dict]) -> dict
  Buckets all posts into strong/weak/normal + reports avg retention score.
- retention_report(learnings_path: Path = Path("aeloria/distribution/learnings.json")) -> dict
  Full report: aggregate + per-post classification + strong/weak ratios.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STRONG_HOOK_THRESHOLD = 0.70  # reach/impressions ratio
WEAK_HOOK_THRESHOLD = 0.30


def retention_score(reach: int, impressions: int) -> float:
    """reach / impressions clamped to [0.0, 1.0]. Zero impressions → 0.0."""
    if impressions <= 0:
        return 0.0
    return max(0.0, min(1.0, reach / impressions))


def classify_hook_performance(reach: int, impressions: int) -> str:
    """Bucket a single post into strong_hook / weak_hook / normal."""
    score = retention_score(reach, impressions)
    if score >= STRONG_HOOK_THRESHOLD:
        return "strong_hook"
    if score <= WEAK_HOOK_THRESHOLD:
        return "weak_hook"
    return "normal"


def aggregate_hook_performance(posts: list[dict]) -> dict:
    """Bucket posts by hook performance. Posts missing reach/impressions are skipped.

    Each post dict may carry: 'post_id', 'reach', 'impressions'.
    Returns dict with keys: counts, shares, avg_retention_score, total_posts, scored_posts.
    """
    counts = {"strong_hook": 0, "weak_hook": 0, "normal": 0}
    scored = 0
    score_sum = 0.0

    for post in posts:
        reach = post.get("reach")
        impressions = post.get("impressions")
        if reach is None or impressions is None:
            continue
        if not isinstance(impressions, (int, float)) or impressions <= 0:
            continue
        cls = classify_hook_performance(int(reach), int(impressions))
        counts[cls] += 1
        score_sum += retention_score(int(reach), int(impressions))
        scored += 1

    total = max(scored, 1)
    return {
        "counts": counts,
        "shares": {k: round(v / total, 4) for k, v in counts.items()},
        "avg_retention_score": round(score_sum / total, 4) if scored else 0.0,
        "total_posts": len(posts),
        "scored_posts": scored,
    }


def retention_report(
    learnings_path: Path = Path("aeloria/distribution/learnings.json"),
) -> dict:
    """Full report: aggregate + per-post classification + strong/weak ratios.

    Reads learnings.json (which has a 'posts' array with per-post metrics) and
    returns a dict. If the file doesn't exist or is malformed, returns an empty
    report with source='missing'.
    """
    out: dict[str, Any] = {
        "aggregate": aggregate_hook_performance([]),
        "per_post": [],
        "source": "missing",
    }

    try:
        raw = json.loads(Path(learnings_path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return out

    posts = raw.get("posts", [])
    if not isinstance(posts, list):
        return out

    out["aggregate"] = aggregate_hook_performance(posts)
    out["per_post"] = [
        {
            "post_id": p.get("post_id"),
            "reach": p.get("reach"),
            "impressions": p.get("impressions"),
            "retention_score": retention_score(
                int(p.get("reach", 0)), int(p.get("impressions", 0))
            ),
            "classification": classify_hook_performance(
                int(p.get("reach", 0)), int(p.get("impressions", 0))
            ),
        }
        for p in posts
        if isinstance(p, dict)
        and p.get("reach") is not None
        and isinstance(p.get("impressions"), (int, float))
    ]
    out["source"] = str(learnings_path)
    return out
