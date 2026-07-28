"""Tests for competitor benchmarking."""
import pytest
from unittest.mock import MagicMock
from aeloria.analytics.competitors import (
    CompetitorTracker,
    CompetitorProfile,
    CompetitorReport,
)


def _make_competitor(username, followers=1000, engagement=0.05, growth=0.02,
                     pillars=None, frequency=5.0):
    return CompetitorProfile(
        username=username,
        follower_count=followers,
        avg_engagement_rate=engagement,
        growth_rate=growth,
        top_pillars=pillars or ["ai_tools"],
        posting_frequency=frequency,
    )


def _make_tracker(competitors=None, our_followers=500, our_engagement=0.08):
    db = MagicMock()
    db.current_follower_count.return_value = our_followers
    db.select_all.return_value = [
        {"reach": 100, "likes": 8, "comments": 0, "shares": 0, "saves": 0}
    ] * 5
    db.select.return_value = []  # no stored competitor profiles

    settings = MagicMock()
    settings.competitor_usernames = competitors if competitors is not None else ["comp1", "comp2"]
    settings.our_username = "aeloria"

    tracker = CompetitorTracker(db, settings)
    return tracker


class TestCompetitorProfile:
    def test_defaults(self):
        p = CompetitorProfile(username="test_user")
        assert p.username == "test_user"
        assert p.follower_count == 0
        assert p.top_pillars == []

    def test_with_data(self):
        p = _make_competitor("big_account", followers=50000, engagement=0.03)
        assert p.follower_count == 50000
        assert p.avg_engagement_rate == 0.03


class TestGenerateReport:
    def test_empty_competitors(self):
        tracker = _make_tracker(competitors=[])
        report = tracker.generate_report()
        assert report.competitors == []
        assert report.content_gaps == []

    def test_fetches_competitor_profiles(self):
        tracker = _make_tracker(competitors=["comp1", "comp2"])
        report = tracker.generate_report()
        assert len(report.competitors) == 2

    def test_top_competitor_by_growth(self):
        tracker = _make_tracker(competitors=["comp1", "comp2"])
        # Mock the fetch to return different growth rates
        tracker._fetch_competitor_profile = lambda u: _make_competitor(
            u, growth=0.05 if u == "comp1" else 0.01
        )
        report = tracker.generate_report()
        assert report.top_competitor == "comp1"

    def test_content_gaps_identified(self):
        tracker = _make_tracker(competitors=["comp1"])
        tracker._fetch_competitor_profile = lambda u: _make_competitor(
            u, pillars=["ai_tools", "ai_news", "productivity"]
        )
        report = tracker.generate_report(our_pillars=["ai_tools", "ai_workflows"])
        # "ai_news" and "productivity" are gaps
        assert "ai_news" in report.content_gaps
        assert "productivity" in report.content_gaps
        assert "ai_tools" not in report.content_gaps  # overlap

    def test_content_overlaps_identified(self):
        tracker = _make_tracker(competitors=["comp1"])
        tracker._fetch_competitor_profile = lambda u: _make_competitor(
            u, pillars=["ai_tools", "ai_workflows", "unique_pillar"]
        )
        report = tracker.generate_report(our_pillars=["ai_tools", "ai_workflows"])
        assert "ai_tools" in report.content_overlaps
        assert "ai_workflows" in report.content_overlaps
        assert "unique_pillar" not in report.content_overlaps

    def test_recommendations_generated(self):
        tracker = _make_tracker(competitors=["comp1"], our_followers=100, our_engagement=0.02)
        tracker._fetch_competitor_profile = lambda u: _make_competitor(
            u, followers=5000, engagement=0.06, growth=0.05
        )
        report = tracker.generate_report()
        assert len(report.recommended_actions) > 0

    def test_engagement_comparison_recommendation(self):
        # Our engagement is much lower than competitors
        tracker = _make_tracker(competitors=["comp1"], our_engagement=0.01)
        tracker._fetch_competitor_profile = lambda u: _make_competitor(
            u, engagement=0.08
        )
        tracker._get_our_metrics = lambda: (100, 0.01)
        report = tracker.generate_report()
        assert any("below competitor" in r for r in report.recommended_actions)

    def test_high_engagement_recommendation(self):
        # Our engagement is much higher than competitors
        tracker = _make_tracker(competitors=["comp1"], our_engagement=0.15)
        tracker._fetch_competitor_profile = lambda u: _make_competitor(
            u, engagement=0.03
        )
        report = tracker.generate_report()
        assert any("exceeds competitor" in r for r in report.recommended_actions)

    def test_report_has_timestamp(self):
        tracker = _make_tracker(competitors=["comp1"])
        report = tracker.generate_report()
        assert report.generated_at  # non-empty

    def test_our_metrics_included(self):
        tracker = _make_tracker(competitors=["comp1"], our_followers=2000, our_engagement=0.10)
        report = tracker.generate_report()
        assert report.our_followers == 2000
        assert report.our_engagement_rate == pytest.approx(0.08)  # from db mock

    def test_default_pillars_used(self):
        tracker = _make_tracker(competitors=["comp1"])
        tracker._fetch_competitor_profile = lambda u: _make_competitor(
            u, pillars=["ai_workflows", "unique_topic"]
        )
        report = tracker.generate_report()  # no our_pillars arg
        assert "unique_topic" in report.content_gaps
        assert "ai_workflows" not in report.content_gaps