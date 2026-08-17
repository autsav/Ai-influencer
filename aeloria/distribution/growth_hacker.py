"""
Growth Hacker Agent — multi-agent pipeline feedback loop.

Adapted from agency-agents/marketing-growth-hacker.md.

Tracks post analytics → updates learnings.json → informs next generation cycle.

K-factor: K = (shares + saves) / max(impressions - (shares + saves), 1)
K > 1.0 = viral loop. K < 0.5 = low viral potential.

learnings.json schema:
  {
    "best_hooks": [{"item": "curiosity_gap", "score": 1.42}, ...],
    "best_times": ["08:00", "12:00", "18:00"],
    "best_hashtag_sets": [{"item": ["#ai...", ...], "score": 0.072}],
    "best_pillars": [{"item": "AI tools + productivity", "score": 0.085}],
    "posts": [{ "post_id", "hook_type", "impressions", ..., "k_factor", "engagement_rate", "recorded_at" }]
  }
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class GrowthHackerAgent:
    """Records post performance and surfaces winning patterns."""

    def __init__(self, learnings_path: Optional[Path] = None):
        self.learnings_path = learnings_path or Path("aeloria/distribution/learnings.json")
        self.learnings_path.parent.mkdir(parents=True, exist_ok=True)
        self.learnings = self._load()

    def _load(self) -> dict:
        if self.learnings_path.exists():
            try:
                return json.loads(self.learnings_path.read_text())
            except json.JSONDecodeError:
                pass
        return self._empty_learnings()

    def _empty_learnings(self) -> dict:
        return {
            "best_hooks": [],
            "best_times": [],
            "best_hashtag_sets": [],
            "best_pillars": [],
            "best_presets": [],
            "posts": [],
            # U3 (2026-08-17): daily trend-radar output. Each entry is a dict
            # {"topic": str, "source": str, "score": float, "scanned_at": iso}.
            "trending_topics": [],
        }

    def _save(self):
        self.learnings_path.write_text(json.dumps(self.learnings, indent=2))

    def record_analytics(
        self,
        post_id: str,
        hook_type: str,
        content_pillar: str,
        impressions: int,
        likes: int,
        comments: int,
        shares: int,
        saves: int,
        preset: str = "",
        hashtags: Optional[list[str]] = None,
        scheduled_time: str = "",
    ) -> dict:
        """Record post performance and update rolling best-of lists."""
        denominator = max(impressions - (shares + saves), 1)
        k_factor = (shares + saves) / denominator if denominator > 0 else 0.0
        engagement_rate = (likes + comments + saves) / max(impressions, 1)

        entry = {
            "post_id": post_id,
            "hook_type": hook_type,
            "content_pillar": content_pillar,
            "preset": preset,
            "impressions": impressions,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "saves": saves,
            "k_factor": round(k_factor, 3),
            "engagement_rate": round(engagement_rate, 4),
            "hashtags": hashtags or [],
            "scheduled_time": scheduled_time,
            "recorded_at": datetime.utcnow().isoformat(),
        }

        self.learnings["posts"].append(entry)
        if len(self.learnings["posts"]) > 500:
            self.learnings["posts"] = self.learnings["posts"][-500:]

        # Update rolling best-of (top 5 per category)
        self._update_best("best_hooks", hook_type, k_factor, hook_type)
        self._update_best("best_pillars", content_pillar, engagement_rate, content_pillar)
        if preset:
            self._update_best("best_presets", preset, engagement_rate, preset)
        if hashtags:
            self._update_best("best_hashtag_sets", json.dumps(sorted(hashtags)), engagement_rate, sorted(hashtags))

        self._save()
        return {"k_factor": k_factor, "engagement_rate": engagement_rate}

    def _update_best(self, key: str, item_key: str, score: float, raw_item):
        current = self.learnings.get(key, [])
        current = [e for e in current if e.get("item_key") != item_key]
        current.append({"item_key": item_key, "item": raw_item, "score": round(score, 4)})
        current.sort(key=lambda x: x["score"], reverse=True)
        self.learnings[key] = current[:5]

    # ── Query interface ──────────────────────────────────────────────────────
    def get_winning_hook_type(self) -> Optional[str]:
        hooks = self.learnings.get("best_hooks", [])
        return hooks[0]["item"] if hooks else None

    def get_winning_content_pillar(self) -> Optional[str]:
        pillars = self.learnings.get("best_pillars", [])
        return pillars[0]["item"] if pillars else None

    def get_winning_posting_times(self) -> list[str]:
        # Default 8am/12pm/6pm if no data
        if self.learnings.get("best_times"):
            return self.learnings["best_times"]
        return ["08:00", "12:00", "18:00"]

    def get_winning_hashtag_set(self) -> list[str]:
        sets = self.learnings.get("best_hashtag_sets", [])
        if sets and isinstance(sets[0].get("item"), list):
            return sets[0]["item"]
        return []

    def get_winning_preset(self) -> Optional[str]:
        presets = self.learnings.get("best_presets", [])
        return presets[0]["item"] if presets else None

    def get_stats(self) -> dict:
        posts = self.learnings.get("posts", [])
        if not posts:
            return {"total_posts": 0, "avg_k_factor": 0, "avg_engagement": 0}
        return {
            "total_posts": len(posts),
            "avg_k_factor": round(sum(p["k_factor"] for p in posts) / len(posts), 3),
            "avg_engagement": round(sum(p["engagement_rate"] for p in posts) / len(posts), 4),
            "viral_posts": sum(1 for p in posts if p["k_factor"] > 1.0),
        }
