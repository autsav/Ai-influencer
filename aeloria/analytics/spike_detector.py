"""Real-time viral spike detection for Instagram posts.

Monitors post engagement metrics hourly. If a post's engagement rate exceeds
a configurable multiple of the account median within the first few hours,
triggers a spike alert — enabling auto-boost (repost to Story, push to other
platforms).

Usage:
    from aeloria.analytics.spike_detector import SpikeDetector, SpikeAlert
    detector = SpikeDetector(db, settings)
    alerts = detector.check_spikes()
    for alert in alerts:
        print(f"🚀 Spike: {alert.post_id} — {alert.engagement_rate:.2f} vs median {alert.account_median:.2f}")
"""
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class SpikeAlert:
    """Alert for a post showing viral engagement."""
    post_id: str
    media_id: str
    engagement_rate: float
    account_median: float
    spike_multiplier: float
    hours_since_post: float
    platform: str = "instagram"
    recommended_action: str = "boost_to_story"

    def __repr__(self):
        return (
            f"SpikeAlert(post={self.post_id}, rate={self.engagement_rate:.3f}, "
            f"median={self.account_median:.3f}, {self.spike_multiplier:.1f}x, "
            f"{self.hours_since_post:.1f}h old)"
        )


class SpikeDetector:
    """Detect posts with engagement significantly above account median.

    Configurable via settings:
    - spike_multiplier: How many times the median to trigger (default 3.0)
    - spike_window_hours: Only check posts within this age window (default 6h)
    - min_metrics_for_median: Minimum posts needed to calculate median (default 5)
    """

    def __init__(self, db, settings):
        self.db = db
        self.settings = settings
        self.spike_multiplier = getattr(settings, "spike_multiplier", 3.0)
        self.spike_window_hours = getattr(settings, "spike_window_hours", 6.0)
        self.min_metrics_for_median = getattr(settings, "min_metrics_for_median", 5)

    def _calculate_engagement_rate(self, metrics: dict) -> float:
        """Calculate engagement rate: (likes + comments + shares + saves) / reach."""
        reach = metrics.get("reach", 0)
        if reach == 0:
            return 0.0
        engagement = (
            metrics.get("likes", 0)
            + metrics.get("comments", 0)
            + metrics.get("shares", 0)
            + metrics.get("saves", 0)
        )
        return engagement / reach

    def _get_account_median_rate(self) -> float:
        """Calculate the median engagement rate across recent posts."""
        try:
            posts = self.db.select_all("post_metrics")
            if not posts or len(posts) < self.min_metrics_for_median:
                return 0.0

            rates = []
            for p in posts:
                m = p if isinstance(p, dict) else {}
                rate = self._calculate_engagement_rate(m)
                if rate > 0:
                    rates.append(rate)

            if len(rates) < self.min_metrics_for_median:
                return 0.0

            rates.sort()
            mid = len(rates) // 2
            if len(rates) % 2 == 0:
                return (rates[mid - 1] + rates[mid]) / 2
            return rates[mid]
        except Exception as e:
            log.warning("Failed to calculate account median: %s", e)
            return 0.0

    def _get_recent_posts(self, window_hours: float) -> list[dict]:
        """Get posts published within the last window_hours."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        try:
            all_posts = self.db.select_all("queue")
            if not all_posts:
                return []
            recent = []
            for p in all_posts:
                if not isinstance(p, dict):
                    continue
                published = p.get("published_at") or p.get("slot_time")
                if not published:
                    continue
                # Parse ISO timestamp
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    if pub_dt > cutoff:
                        recent.append(p)
                except (ValueError, AttributeError):
                    continue
            return recent
        except Exception as e:
            log.warning("Failed to get recent posts: %s", e)
            return []

    def _get_post_metrics(self, post_id: str) -> dict | None:
        """Get the latest metrics for a post."""
        try:
            rows = self.db.select("post_metrics", {"queue_id": post_id}, limit=1)
            if rows:
                return rows[0]
        except Exception:
            pass
        return None

    def check_spikes(self) -> list[SpikeAlert]:
        """Check all recent posts for viral spikes.

        Returns a list of SpikeAlert for posts exceeding the spike multiplier.
        """
        median = self._get_account_median_rate()
        if median == 0.0:
            log.info("Spike detection skipped: insufficient data for median")
            return []

        recent = self._get_recent_posts(self.spike_window_hours)
        if not recent:
            return []

        alerts = []
        for post in recent:
            post_id = post.get("id", "")
            metrics = self._get_post_metrics(post_id)
            if not metrics:
                continue

            rate = self._calculate_engagement_rate(metrics)
            if rate == 0:
                continue

            multiplier = rate / median
            if multiplier >= self.spike_multiplier:
                # Calculate hours since post
                published = post.get("published_at") or post.get("slot_time", "")
                hours = 0.0
                try:
                    pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                    hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
                except (ValueError, AttributeError):
                    pass

                alert = SpikeAlert(
                    post_id=post_id,
                    media_id=str(metrics.get("media_id", "")),
                    engagement_rate=rate,
                    account_median=median,
                    spike_multiplier=multiplier,
                    hours_since_post=hours,
                )
                alerts.append(alert)
                log.info("🚀 Spike detected: %s (%.1fx median)", post_id, multiplier)

        return alerts