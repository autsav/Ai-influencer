"""Tests for viral spike detection."""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta
from aeloria.analytics.spike_detector import SpikeDetector, SpikeAlert


def _make_metrics(likes=10, comments=2, shares=1, saves=3, reach=100):
    return {"likes": likes, "comments": comments, "shares": shares, "saves": saves, "reach": reach}


def _make_post(post_id, hours_ago=2, published=True):
    pub_time = (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()
    return {"id": post_id, "published_at": pub_time if published else None}


class TestEngagementRate:
    def test_basic_rate(self):
        det = SpikeDetector(MagicMock(), MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        rate = det._calculate_engagement_rate(_make_metrics(likes=16, reach=100))
        assert rate == pytest.approx(0.22)  # (16+2+1+3)/100

    def test_zero_reach_returns_zero(self):
        det = SpikeDetector(MagicMock(), MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        rate = det._calculate_engagement_rate(_make_metrics(reach=0))
        assert rate == 0.0

    def test_missing_fields(self):
        det = SpikeDetector(MagicMock(), MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        rate = det._calculate_engagement_rate({"reach": 100})
        assert rate == 0.0


class TestAccountMedian:
    def test_insufficient_data_returns_zero(self):
        db = MagicMock()
        db.select_all.return_value = []
        det = SpikeDetector(db, MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        det.min_metrics_for_median = 5
        assert det._get_account_median_rate() == 0.0

    def test_calculates_median(self):
        db = MagicMock()
        db.select_all.return_value = [
            _make_metrics(likes=10, reach=100),   # 0.16
            _make_metrics(likes=20, reach=100),   # 0.26
            _make_metrics(likes=30, reach=100),   # 0.36
            _make_metrics(likes=40, reach=100),   # 0.46
            _make_metrics(likes=50, reach=100),   # 0.56
        ]
        det = SpikeDetector(db, MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        det.min_metrics_for_median = 5
        median = det._get_account_median_rate()
        assert median == pytest.approx(0.36)  # middle value


class TestCheckSpikes:
    def test_no_median_returns_empty(self):
        db = MagicMock()
        db.select_all.return_value = []
        det = SpikeDetector(db, MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        alerts = det.check_spikes()
        assert alerts == []

    def test_spike_detected(self):
        db = MagicMock()
        # Account median: 5 posts with ~0.16 engagement rate
        db.select_all.return_value = [
            _make_metrics(likes=10, reach=100),
            _make_metrics(likes=10, reach=100),
            _make_metrics(likes=10, reach=100),
            _make_metrics(likes=10, reach=100),
            _make_metrics(likes=10, reach=100),
        ]
        # First call: return the 5 posts for median
        # Second call: return a recent post
        # We need to handle the two calls to select_all differently
        # Use side_effect
        recent_post = _make_post("post-1", hours_ago=2)
        db.select_all.side_effect = [
            [  # First call: for median
                {"reach": 100, "likes": 10, "comments": 2, "shares": 1, "saves": 3},
            ] * 5,
            [recent_post],  # Second call: recent posts
        ]
        # get_post_metrics returns a viral post: 0.80 engagement rate (5x median of 0.16)
        db.select.return_value = [_make_metrics(likes=60, comments=10, shares=5, saves=5, reach=100)]

        det = SpikeDetector(db, MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        det.spike_multiplier = 3.0
        det.min_metrics_for_median = 5

        alerts = det.check_spikes()
        assert len(alerts) == 1
        assert alerts[0].post_id == "post-1"
        assert alerts[0].spike_multiplier >= 3.0

    def test_no_spike_for_normal_post(self):
        db = MagicMock()
        db.select_all.side_effect = [
            [{"reach": 100, "likes": 10, "comments": 2, "shares": 1, "saves": 3}] * 5,
            [_make_post("post-1", hours_ago=2)],
        ]
        # Normal post: 0.16 rate, same as median
        db.select.return_value = [_make_metrics(likes=10, reach=100)]

        det = SpikeDetector(db, MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        det.spike_multiplier = 3.0
        det.min_metrics_for_median = 5

        alerts = det.check_spikes()
        assert alerts == []

    def test_old_posts_excluded(self):
        db = MagicMock()
        db.select_all.side_effect = [
            [{"reach": 100, "likes": 10, "comments": 2, "shares": 1, "saves": 3}] * 5,
            [_make_post("post-old", hours_ago=24)],  # 24h old, outside 6h window
        ]
        db.select.return_value = [_make_metrics(likes=80, reach=100)]

        det = SpikeDetector(db, MagicMock(spike_multiplier=3.0, spike_window_hours=6.0, min_metrics_for_median=5))
        det.spike_multiplier = 3.0
        det.spike_window_hours = 6.0
        det.min_metrics_for_median = 5

        alerts = det.check_spikes()
        assert alerts == []


class TestSpikeAlert:
    def test_repr(self):
        alert = SpikeAlert(
            post_id="abc", media_id="123",
            engagement_rate=0.5, account_median=0.1,
            spike_multiplier=5.0, hours_since_post=3.0,
        )
        r = repr(alert)
        assert "abc" in r
        assert "5.0x" in r