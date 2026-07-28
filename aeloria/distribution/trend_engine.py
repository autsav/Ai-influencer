"""Trend-responsive content engine — auto-detect trending AI tools and generate same-day content.

Scans sources (X/Twitter, Product Hunt, Hacker News, Google Trends) for trending
AI tools and topics. When a trend matches our content pillars, generates a brief
for same-day reactive content and inserts it into the calendar.

Usage:
    from aeloria.distribution.trend_engine import TrendEngine, TrendSignal
    engine = TrendEngine(db, settings)
    trends = engine.scan()
    for t in trends:
        print(f"🔥 {t.topic} — {t.source} — {t.urgency}")
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import Counter

log = logging.getLogger(__name__)

# Keywords that match our content pillars
_PILLAR_KEYWORDS = {
    "ai_workflows": ["workflow", "automation", "automate", "pipeline", "integration", "zapier", "n8n", "make.com"],
    "ai_tools": ["tool", "app", "platform", "launch", "release", "startup", "product", "feature"],
    "case_studies": ["case study", "results", "roi", "savings", "efficiency", "case"],
    "founder_lifestyle": ["founder", "entrepreneur", "startup", "solopreneur", "remote work"],
    "future_of_business": ["future", "replace", "jobs", "industry", "transform", "disrupt"],
}

# AI-specific keywords that indicate a trend is relevant
_AI_KEYWORDS = {"ai", "artificial intelligence", "llm", "gpt", "claude", "gemini",
                "machine learning", "ml", "agent", "copilot", "chatbot", "automation"}


@dataclass
class TrendSignal:
    """A detected trending topic relevant to our content."""
    topic: str
    source: str  # "x", "producthunt", "hackernews", "google_trends"
    url: str = ""
    score: float = 0.0  # relevance score 0-1
    pillar: str = ""  # matched content pillar
    urgency: str = "normal"  # "high", "normal", "low"
    detected_at: str = ""
    description: str = ""

    def __post_init__(self):
        if not self.detected_at:
            self.detected_at = datetime.now(timezone.utc).isoformat()


class TrendEngine:
    """Scan external sources for trending AI content.

    In production, this fetches from X/Twitter API, Product Hunt API,
    Hacker News API, and Google Trends. For now, it provides the framework
    with a keyword-based relevance scorer.
    """

    def __init__(self, db=None, settings=None):
        self.db = db
        self.settings = settings
        self.min_score = getattr(settings, "trend_min_score", 0.5)

    def _score_relevance(self, text: str) -> tuple[float, str]:
        """Score how relevant a trend is to our content pillars.

        Returns (score 0-1, matched_pillar).
        """
        text_lower = text.lower()
        words = set(text_lower.split())

        # Must contain at least one AI keyword
        has_ai = any(kw in text_lower for kw in _AI_KEYWORDS)
        if not has_ai:
            return 0.0, ""

        # Score by pillar keyword matches
        best_pillar = ""
        best_score = 0.0

        for pillar, keywords in _PILLAR_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_lower)
            if matches > 0:
                score = min(matches / 3.0, 1.0)  # cap at 1.0
                if score > best_score:
                    best_score = score
                    best_pillar = pillar

        # Boost score if AI keyword is prominent
        if has_ai and best_score > 0:
            best_score = min(best_score + 0.2, 1.0)

        return best_score, best_pillar

    def _determine_urgency(self, score: float, source: str) -> str:
        """Determine urgency level based on score and source."""
        if score >= 0.8 and source in ("x", "producthunt"):
            return "high"
        if score >= 0.5:
            return "normal"
        return "low"

    def scan_x_trends(self) -> list[TrendSignal]:
        """Scan X/Twitter for trending AI topics.

        In production: calls X API v2 trending topics.
        Stub: returns empty list (populate via API integration).
        """
        return []

    def scan_product_hunt(self) -> list[TrendSignal]:
        """Scan Product Hunt for new AI product launches.

        In production: calls Product Hunt API.
        Stub: returns empty list.
        """
        return []

    def scan_hackernews(self) -> list[TrendSignal]:
        """Scan Hacker News for AI-related trending posts.

        In production: calls HN Algolia search API.
        Stub: returns empty list.
        """
        return []

    def scan(self, raw_trends: list[dict] | None = None) -> list[TrendSignal]:
        """Scan all sources and return relevant trend signals.

        Args:
            raw_trends: Optional list of pre-fetched trend dicts with
                       "topic", "source", "url", "description" keys.
                       If None, calls individual scan methods.

        Returns:
            List of TrendSignal objects sorted by score (descending)
        """
        signals = []

        if raw_trends:
            for t in raw_trends:
                topic = t.get("topic", "")
                source = t.get("source", "unknown")
                score, pillar = self._score_relevance(topic + " " + t.get("description", ""))

                if score >= self.min_score:
                    signals.append(TrendSignal(
                        topic=topic,
                        source=source,
                        url=t.get("url", ""),
                        score=score,
                        pillar=pillar,
                        urgency=self._determine_urgency(score, source),
                        description=t.get("description", ""),
                    ))
        else:
            # Call individual source scanners
            signals.extend(self.scan_x_trends())
            signals.extend(self.scan_product_hunt())
            signals.extend(self.scan_hackernews())

        # Sort by score descending
        signals.sort(key=lambda s: s.score, reverse=True)

        log.info("Trend scan: found %d relevant signals (min_score=%.2f)", len(signals), self.min_score)
        return signals

    def generate_reactive_brief(self, trend: TrendSignal) -> dict:
        """Generate a content brief for same-day reactive content.

        Args:
            trend: A TrendSignal to respond to

        Returns:
            Brief dict ready for the generation pipeline
        """
        brief = {
            "id": f"trend-{trend.topic[:20].replace(' ', '-').lower()}-{trend.detected_at[:10]}",
            "prompt_seed": (
                f"Aeloria reacting to {trend.topic}, "
                f"showing excitement and curiosity about this new AI development, "
                f"modern workspace, looking at her laptop screen"
            ),
            "pillar": trend.pillar,
            "caption_angle": f"Hot take on {trend.topic} — why it matters for your business",
            "slot_type": "static",
            "slot_day": trend.detected_at[:10],
            "pillar_match": trend.pillar,
            "trend_topic": trend.topic,
            "trend_url": trend.url,
            "trend_source": trend.source,
            "trend_score": trend.score,
            "trend_urgency": trend.urgency,
            "reactive": True,
        }

        log.info("Generated reactive brief for trend: %s (pillar=%s, urgency=%s)",
                 trend.topic, trend.pillar, trend.urgency)
        return brief