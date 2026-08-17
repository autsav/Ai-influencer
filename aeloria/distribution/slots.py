"""Per-platform best-slot timing with live learning from growth_hacker metrics.

Static defaults (`SLOT_HOUR_UTC`) act as fallback when learnings.json lacks
enough data per niche. Once a niche accumulates ≥`LEARNED_THRESHOLD` posts,
the optimizer picks the highest-scoring learned hour for (niche, day, audience).

Anti-batch minute offset: 9-value grid (0/13/17/23/27/33/37/43/47) randomizes
the publish minute to avoid Instagram's batch-publish detection pattern.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from typing import Optional

SLOT_HOUR_UTC = {"story": 9, "static": 17, "reel": 18}
DEFAULT_HOUR = 12

# Anti-batch grid: prime-ish minutes, < 60, 9 distinct values.
# Rationale: IG flags accounts that publish at exact :00 across many posts;
# the 9-value grid spreads across a 60-min window without obvious patterns.
ANTI_BATCH_MINUTES = [0, 13, 17, 23, 27, 33, 37, 43, 47]

# Need ≥10 posts in a niche before trusting learned hour over static fallback.
LEARNED_THRESHOLD = 10


def _load_learnings(learnings_path: Optional[Path]) -> dict:
    if learnings_path and learnings_path.exists():
        try:
            return json.loads(learnings_path.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _post_count_for_niche(learnings: dict, niche: str, day: Optional[str], audience: Optional[str]) -> int:
    """Count posts in `learnings["posts"]` matching niche/day/audience.

    `posts` entries may not carry niche/audience/day_of_week yet (legacy schema);
    if so, count all posts for that niche.
    """
    posts = learnings.get("posts", [])
    matched = 0
    for p in posts:
        if p.get("niche") and p["niche"] != niche:
            continue
        if day is not None and p.get("day_of_week") and p["day_of_week"] != day:
            continue
        if audience is not None and p.get("audience") and p["audience"] != audience:
            continue
        matched += 1
    return matched


def _learned_hour(learnings: dict, niche: str, day: str, audience: str) -> Optional[int]:
    """Pick the highest-scoring learned hour for (niche, day, audience).

    Returns None if no matching learned slot exists.
    """
    candidates = [
        e for e in learnings.get("best_times", [])
        if isinstance(e, dict)
        and e.get("niche") == niche
        and e.get("day") == day
        and e.get("audience") == audience
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda e: e.get("score", 0), reverse=True)
    return int(candidates[0]["hour"])


def _day_name(slot_day: str) -> str:
    """YYYY-MM-DD → lowercased weekday name."""
    dt = datetime.strptime(slot_day, "%Y-%m-%d")
    return dt.strftime("%A").lower()


def _combine(day_str: str, hour: int, minute: int) -> str:
    day = datetime.strptime(day_str, "%Y-%m-%d").date()
    return datetime.combine(day, dtime(hour=hour, minute=minute), tzinfo=timezone.utc).isoformat()


def learn_best_time(
    niche: str,
    slot_day: str,
    audience: str,
    slot_type: str = "reel",
    learnings_path: Optional[Path] = None,
) -> str:
    """Return ISO-8601 UTC timestamp for `slot_day` using learned hour if available.

    Lookup order:
      1. (niche, day-of-week, audience) → highest-scoring learned hour
      2. Static default from `slot_type`
    """
    learnings = _load_learnings(learnings_path)
    day_name = _day_name(slot_day)

    # Need ≥`LEARNED_THRESHOLD` posts in this niche before trusting learned hour.
    post_count = _post_count_for_niche(learnings, niche, day_name, audience)
    if post_count >= LEARNED_THRESHOLD:
        hour = _learned_hour(learnings, niche, day_name, audience)
        if hour is not None:
            minute = random.choice(ANTI_BATCH_MINUTES)
            return _combine(slot_day, hour, minute)

    # Fallback: static defaults.
    hour = SLOT_HOUR_UTC.get(slot_type, DEFAULT_HOUR)
    minute = random.choice(ANTI_BATCH_MINUTES)
    return _combine(slot_day, hour, minute)


def best_time(
    platform: str,
    slot_type: str,
    slot_day: str,
    niche: Optional[str] = None,
    audience: Optional[str] = None,
    learnings_path: Optional[Path] = None,
) -> str:
    """Return an ISO-8601 UTC timestamp for the slot on slot_day (YYYY-MM-DD).

    `platform` is accepted for future per-platform refinement; ignored today.
    When `niche` + `audience` are supplied and learnings.json has ≥
    `LEARNED_THRESHOLD` posts for that niche, the learned hour is used;
    otherwise the static default applies. Anti-batch minute offset is
    always applied (0/13/17/23/27/33/37/43/47 grid).
    """
    if niche and audience:
        return learn_best_time(
            niche=niche,
            slot_day=slot_day,
            audience=audience,
            slot_type=slot_type,
            learnings_path=learnings_path,
        )

    hour = SLOT_HOUR_UTC.get(slot_type, DEFAULT_HOUR)
    minute = random.choice(ANTI_BATCH_MINUTES)
    return _combine(slot_day, hour, minute)
