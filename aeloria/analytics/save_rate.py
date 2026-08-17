"""
Save-rate-first KPI analytics. Save rate is the algorithm's primary signal
in 2026 IG (3-4x comment weight). Aggregate from learnings.json["posts"].

Public functions:
- save_rate_per_pillar(posts: list[dict]) -> dict[str, float]
- save_rate_per_hook_type(posts: list[dict]) -> dict[str, float]
- rolling_save_rate(posts: list[dict], days: int = 7) -> float
- top_posts_by_save_rate(posts: list[dict], n: int = 10) -> list[dict]
- save_rate_report(learnings_path: Path = Path("aeloria/distribution/learnings.json")) -> dict
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_LEARNINGS_PATH = Path("aeloria/distribution/learnings.json")


def _save_rate(post: dict) -> float | None:
    """saves/impressions for a single post. None when impressions==0."""
    impressions = post.get("impressions") or 0
    saves = post.get("saves") or 0
    if impressions <= 0:
        return None
    return saves / impressions


def save_rate_per_pillar(posts: list[dict]) -> dict[str, float]:
    """Return {pillar: avg_save_rate} across all posts with impressions>0."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        rate = _save_rate(post)
        if rate is None:
            continue
        pillar = post.get("content_pillar") or "unknown"
        buckets[pillar].append(rate)
    return {pillar: sum(rs) / len(rs) for pillar, rs in buckets.items() if rs}


def save_rate_per_hook_type(posts: list[dict]) -> dict[str, float]:
    """Return {hook_type: avg_save_rate}."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        rate = _save_rate(post)
        if rate is None:
            continue
        hook = post.get("hook_type") or "unknown"
        buckets[hook].append(rate)
    return {hook: sum(rs) / len(rs) for hook, rs in buckets.items() if rs}


def rolling_save_rate(posts: list[dict], days: int = 7) -> float:
    """Avg save_rate for posts recorded within last N days. 0.0 when none."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rates: list[float] = []
    for post in posts:
        ts_raw = post.get("recorded_at")
        if not ts_raw:
            continue
        try:
            ts = datetime.fromisoformat(ts_raw)
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < cutoff:
            continue
        rate = _save_rate(post)
        if rate is not None:
            rates.append(rate)
    if not rates:
        return 0.0
    return sum(rates) / len(rates)


def top_posts_by_save_rate(posts: list[dict], n: int = 10) -> list[dict]:
    """Return top-N posts sorted by save_rate desc. Each item gets a save_rate field."""
    enriched: list[dict[str, Any]] = []
    for post in posts:
        rate = _save_rate(post)
        if rate is None:
            continue
        enriched.append({**post, "save_rate": rate})
    enriched.sort(key=lambda p: p["save_rate"], reverse=True)
    return enriched[:n]


def save_rate_report(
    learnings_path: Path = DEFAULT_LEARNINGS_PATH,
) -> dict:
    """Load learnings.json, compute all aggregates, return report dict."""
    if not learnings_path.exists():
        return {
            "per_pillar": {},
            "per_hook_type": {},
            "rolling_7d": 0.0,
            "top_posts": [],
            "post_count": 0,
            "source": str(learnings_path),
        }
    data = json.loads(learnings_path.read_text())
    posts = data.get("posts", [])
    return {
        "per_pillar": save_rate_per_pillar(posts),
        "per_hook_type": save_rate_per_hook_type(posts),
        "rolling_7d": rolling_save_rate(posts, days=7),
        "top_posts": top_posts_by_save_rate(posts, n=10),
        "post_count": len(posts),
        "source": str(learnings_path),
    }