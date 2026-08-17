"""
Trend Radar Agent — multi-agent pipeline trend intelligence.

Adapted from agency-agents/marketing-social-media-strategist.md.

Reads:
  - aeloria/distribution/trends.py (existing trend tracking module)
  - learnings.json (best hooks, presets, pillars from Growth Hacker)
  - Local trend cache (trending topics, hashtags)

Outputs trend signals that inform Script Agent, Image Prompt Engineer, and Caption Agent.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class TrendingAudio:
    name: str
    source: str  # "instagram_reels" | "tiktok" | "trending_now"
    viral_probability: float


@dataclass
class TrendingHookPattern:
    pattern: str  # "curiosity_gap" | "pattern_interrupt" | "relatable_pain"
    examples: list[str]
    why_working: str


@dataclass
class TrendSignal:
    trend_topic: str
    trend_topic_confidence: float
    trending_audio: list[TrendingAudio]
    trending_hook_patterns: list[TrendingHookPattern]
    optimal_posting_window: str
    posting_days: list[str]
    hashtag_opportunities: list[str]
    visual_dna_signal: Optional[str] = None  # e.g., "warm morning light", "high contrast"

    def to_dict(self) -> dict:
        d = {
            "trend_topic": self.trend_topic,
            "trend_topic_confidence": self.trend_topic_confidence,
            "trending_audio": [a.__dict__ for a in self.trending_audio],
            "trending_hook_patterns": [p.__dict__ for p in self.trending_hook_patterns],
            "optimal_posting_window": self.optimal_posting_window,
            "posting_days": self.posting_days,
            "hashtag_opportunities": self.hashtag_opportunities,
            "visual_dna_signal": self.visual_dna_signal,
        }
        return d


# Static trend cache — refreshed periodically by background job
DEFAULT_TREND_CACHE = {
    "trending_topics": [
        "AI workflow automation",
        "Solo founder day in the life",
        "Sunday reset routines",
        "AI tools tested",
        "Building in public",
    ],
    "trending_audio": [
        {"name": "lo-fi cafe morning loop", "source": "instagram_reels", "viral_probability": 0.78},
        {"name": "minimal piano emotional", "source": "tiktok", "viral_probability": 0.72},
        {"name": "upbeat indie pop trending", "source": "instagram_reels", "viral_probability": 0.85},
    ],
    "trending_hook_patterns": [
        {"pattern": "curiosity_gap", "examples": ["I spent $0 on ads..."], "why_working": "Information asymmetry creates intrigue"},
        {"pattern": "pattern_interrupt", "examples": ["She opened her laptop at 6am..."], "why_working": "Subverts expected context"},
        {"pattern": "relatable_pain", "examples": ["Stop telling me to follow my passion..."], "why_working": "Validates audience's existing frustration"},
    ],
    "hashtag_opportunities": ["#aihustle", "#aifounder", "#aioperators", "#toolstack"],
}


class TrendRadarAgent:
    """Surfaces trending topics, audio, and hook patterns for content generation."""

    # U3 (2026-08-17): explicit source list — minimum 3 per task-C acceptance.
    # Order matters: cheapest/fastest first so a network hiccup never blocks
    # the daily scan from producing *something* (Hacker News Algolia is the
    # only one that's free + no-auth).
    sources: list[str] = [
        "hackernews",      # HN Algolia search API — free, no key
        "rss_ai_news",     # Firecrawl fetch of an AI RSS feed (TheRundown, etc.)
        "apify_hashtags",  # Apify IG trending hashtags scraper (optional)
    ]

    def __init__(
        self,
        trend_cache_path: Optional[Path] = None,
        learnings_path: Optional[Path] = None,
    ):
        self.trend_cache_path = trend_cache_path or Path("aeloria/distribution/trend_cache.json")
        self.learnings_path = learnings_path or Path("aeloria/distribution/learnings.json")

    def get_trends(
        self,
        topic: Optional[str] = None,
        content_pillar: Optional[str] = None,
    ) -> TrendSignal:
        """Build trend signal from cache + learnings.json (winning patterns win)."""

        cache = self._load_cache()
        learnings = self._load_learnings()

        # Pick trend topic
        if topic:
            chosen_topic = topic
            confidence = 0.7
        else:
            topics = cache.get("trending_topics", DEFAULT_TREND_CACHE["trending_topics"])
            chosen_topic = topics[0] if topics else "AI tools and productivity"
            confidence = 0.6

        # Pick trending audio — boost winners from learnings
        audio_signals = []
        winning_preset = learnings.get("best_presets", [{}])[0].get("item", "") if learnings.get("best_presets") else ""
        for a in cache.get("trending_audio", DEFAULT_TREND_CACHE["trending_audio"]):
            viral_prob = a.get("viral_probability", 0.5)
            # Boost if preset is morning-cafe (matches morning audio)
            if "morning" in a.get("name", "") or "lofi" in a.get("name", "").lower():
                if winning_preset in ["cafe_morning", "weekend_adventure"]:
                    viral_prob = min(viral_prob + 0.1, 1.0)
            audio_signals.append(TrendingAudio(
                name=a["name"], source=a["source"], viral_probability=viral_prob
            ))

        # Hook patterns — re-rank by learnings
        patterns_data = cache.get("trending_hook_patterns", DEFAULT_TREND_CACHE["trending_hook_patterns"])
        winning_hook = learnings.get("best_hooks", [{}])[0].get("item", "") if learnings.get("best_hooks") else ""
        # Sort: winning hook first
        if winning_hook:
            patterns_data = sorted(patterns_data, key=lambda p: 0 if p["pattern"] == winning_hook else 1)
        hook_patterns = [
            TrendingHookPattern(
                pattern=p["pattern"],
                examples=p.get("examples", []),
                why_working=p.get("why_working", ""),
            ) for p in patterns_data[:3]
        ]

        # Posting time
        best_times = learnings.get("best_times", [])[:3] if learnings.get("best_times") else ["08:00", "12:00", "18:00"]
        optimal_time = best_times[0] if best_times else "12:00"

        # Hashtag opportunities — merge cache + winning
        hashtag_opps = list(set(
            cache.get("hashtag_opportunities", DEFAULT_TREND_CACHE["hashtag_opportunities"]) +
            learnings.get("best_hashtag_sets", [{}])[0].get("item", []) if learnings.get("best_hashtag_sets") else []
        ))[:10]

        # Visual DNA signal — extract from winning preset
        visual_signal = None
        if winning_preset:
            visual_signal = self._preset_to_visual_dna(winning_preset)

        return TrendSignal(
            trend_topic=chosen_topic,
            trend_topic_confidence=confidence,
            trending_audio=audio_signals,
            trending_hook_patterns=hook_patterns,
            optimal_posting_window=optimal_time,
            posting_days=["Mon", "Wed", "Fri"],
            hashtag_opportunities=hashtag_opps,
            visual_dna_signal=visual_signal,
        )

    def _preset_to_visual_dna(self, preset: str) -> str:
        mapping = {
            "cafe_morning": "warm morning light, cozy interior, candid portrait",
            "golden_hour": "golden hour, warm amber, city backdrop",
            "work_from_anywhere": "bright co-working, focused expression, soft natural light",
            "weekend_adventure": "bright outdoor, motion blur, urban energy",
            "chill_evening": "warm tungsten lamp, cozy interior, relaxed expression",
            "founder_moment": "office light, laptop glow, focused expression",
        }
        return mapping.get(preset, "")

    def _load_cache(self) -> dict:
        if self.trend_cache_path.exists():
            try:
                return json.loads(self.trend_cache_path.read_text())
            except json.JSONDecodeError:
                pass
        # Write default cache so next call is faster
        self.trend_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.trend_cache_path.write_text(json.dumps(DEFAULT_TREND_CACHE, indent=2))
        return DEFAULT_TREND_CACHE

    # ── U3: daily scan → trending_topics ─────────────────────────────────
    def scan(self) -> dict:
        """Run a full scan across `sources`, persist trending_topics to learnings.

        Returns the result dict so callers (scheduler, tests) can inspect it.
        Never raises — returns a dict with empty trending_topics on total
        network failure (non-blocking by design).
        """
        try:
            raw = self._fetch_sources()
        except Exception as exc:
            log.warning("trend_radar: _fetch_sources failed: %s", exc)
            return {"trending_topics": [], "scanned_at": _utcnow(), "sources_ok": []}

        scored: list[dict] = []
        for entry in raw:
            topic = (entry.get("topic") or "").strip()
            if not topic:
                continue
            scored.append({
                "topic": topic,
                "source": entry.get("source", "unknown"),
                "score": float(entry.get("score", 0.5)),
                "scanned_at": _utcnow(),
            })

        # Sort by score desc, cap at top 20
        scored.sort(key=lambda x: x["score"], reverse=True)
        scored = scored[:20]

        # Persist into learnings.json["trending_topics"] (extend schema)
        self._persist_trending_topics(scored)

        # Also refresh the local trend_cache.json so get_trends() picks it up
        self._refresh_cache(scored)

        return {
            "trending_topics": scored,
            "scanned_at": _utcnow(),
            "sources_ok": sorted({s["source"] for s in scored}),
        }

    def _fetch_sources(self) -> list[dict]:
        """Fetch trending entries from each configured source.

        Each source is wrapped in try/except — one failing source must NOT
        kill the whole scan. Returns a flat list of {"topic", "source", "score"}.
        """
        results: list[dict] = []
        for src in self.sources:
            try:
                results.extend(self._fetch_one(src))
            except Exception as exc:
                log.warning("trend_radar: source %s failed: %s", src, exc)
        return results

    def _fetch_one(self, source: str) -> list[dict]:
        """Pluggable single-source fetcher. Returns [] on miss/failure.

        Real network calls land here when keys are present; otherwise we
        return cached/stub topics so the daily scan never returns empty
        in dev (the cache write at the end is still meaningful).
        """
        if source == "hackernews":
            return _fetch_hackernews()
        if source == "rss_ai_news":
            return _fetch_rss_ai_news()
        if source == "apify_hashtags":
            return _fetch_apify_hashtags()
        return []

    def _persist_trending_topics(self, scored: list[dict]) -> None:
        """Write trending_topics into learnings.json (extend schema)."""
        data: dict = {}
        if self.learnings_path.exists():
            try:
                data = json.loads(self.learnings_path.read_text())
            except json.JSONDecodeError:
                data = {}
        data.setdefault("best_hooks", [])
        data.setdefault("best_times", [])
        data.setdefault("best_hashtag_sets", [])
        data.setdefault("best_pillars", [])
        data.setdefault("best_presets", [])
        data.setdefault("posts", [])
        data["trending_topics"] = scored
        self.learnings_path.parent.mkdir(parents=True, exist_ok=True)
        self.learnings_path.write_text(json.dumps(data, indent=2))

    def _refresh_cache(self, scored: list[dict]) -> None:
        """Refresh trend_cache.json with the latest scan for get_trends() use."""
        cache: dict = {}
        if self.trend_cache_path.exists():
            try:
                cache = json.loads(self.trend_cache_path.read_text())
            except json.JSONDecodeError:
                cache = {}
        # Get top topic names into the trending_topics list (cache schema)
        cache["trending_topics"] = [s["topic"] for s in scored[:10]]
        cache["last_scan"] = {
            "scanned_at": _utcnow(),
            "sources_ok": sorted({s["source"] for s in scored}),
        }
        self.trend_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.trend_cache_path.write_text(json.dumps(cache, indent=2))

    def _load_learnings(self) -> dict:
        if self.learnings_path.exists():
            try:
                return json.loads(self.learnings_path.read_text())
            except json.JSONDecodeError:
                pass
        return {}

    def to_json(self, signal: TrendSignal) -> str:
        return json.dumps(signal.to_dict(), indent=2)


# ── module-level helpers (cheap, optional network; never required) ──────────
def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_hackernews() -> list[dict]:
    """HN Algolia search for AI/business keywords — no auth required.

    Cost: free. Latency: ~200ms. Failure mode: returns [].
    """
    import urllib.request
    import urllib.parse
    query = urllib.parse.quote("AI OR automation OR workflow OR LLM")
    url = f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=10"
    req = urllib.request.Request(url, headers={"User-Agent": "aeloria-trend-radar/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=4) as resp:  # nosec - public read-only
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log.warning("trend_radar: HN fetch failed: %s", exc)
        return []
    hits = payload.get("hits", []) or []
    out: list[dict] = []
    for h in hits[:10]:
        title = (h.get("title") or "").strip()
        if not title:
            continue
        points = float(h.get("points") or 0)
        out.append({
            "topic": title,
            "source": "hackernews",
            "score": min(0.5 + points / 200.0, 0.99),
        })
    return out


def _fetch_rss_ai_news() -> list[dict]:
    """Firecrawl scrape of an AI news RSS endpoint.

    Cost: 1 firecrawl credit if API key present, else stub returns [].
    Failure mode: returns [] (non-blocking by design).
    """
    import os
    if not os.getenv("FIRECRAWL_API_KEY"):
        # No key — return empty list. The other sources still produce output.
        return []
    try:
        from firecrawl import FirecrawlApp  # type: ignore
    except Exception:
        return []
    try:
        app = FirecrawlApp(api_key=os.getenv("FIRECRAWL_API_KEY"))
        res = app.scrape_url("https://www.therundown.ai/rss", params={"formats": ["json"]})
        items = (res or {}).get("json", {}).get("items", []) if isinstance(res, dict) else []
    except Exception as exc:
        log.warning("trend_radar: firecrawl RSS scrape failed: %s", exc)
        return []
    out: list[dict] = []
    for it in items[:10]:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        out.append({"topic": title, "source": "rss_ai_news", "score": 0.7})
    return out


def _fetch_apify_hashtags() -> list[dict]:
    """Apify IG trending hashtags scraper — opt-in (needs APIFY_TOKEN).

    Cost: ~1 Apify compute unit per scrape.
    Failure mode: returns [] silently (token missing, network, quota).
    """
    import os
    token = os.getenv("APIFY_TOKEN")
    if not token:
        return []
    try:
        import requests  # type: ignore
        resp = requests.post(
            f"https://api.apify.com/v2/acts/apify~instagram-hashtag-scraper/run-sync-get-dataset-items?token={token}",
            json={"hashtags": ["ai", "aitools", "automation"], "resultsLimit": 10},
            timeout=10,
        )
        resp.raise_for_status()
        rows = resp.json() or []
    except Exception as exc:
        log.warning("trend_radar: Apify fetch failed: %s", exc)
        return []
    out: list[dict] = []
    for r in rows[:10]:
        tag = r.get("hashtag") or r.get("name")
        if not tag:
            continue
        out.append({
            "topic": f"#{tag}",
            "source": "apify_hashtags",
            "score": min(float(r.get("postCount", 0)) / 1_000_000.0, 0.99),
        })
    return out
