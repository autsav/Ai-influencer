"""TDD tests for TASK C — U3: trend_radar → daily brief wiring.

Coverage:
  - TrendRadarAgent populates ≥3 sources and writes to learnings.json
  - learnings.json schema extended with trending_topics key
  - scheduler.build_scheduler wires daily_trend_scan job at 06:00 UTC
  - MultiAgentPipeline.plan (or run) consumes trending_topics from learnings
  - If scan fails or no trending_topics, pipeline proceeds (non-blocking)
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aeloria.distribution.trend_radar import TrendRadarAgent
from aeloria.distribution.growth_hacker import GrowthHackerAgent


# ─── 1. TrendRadarAgent: ≥3 sources + writes trending_topics ─────────────────


class TestTrendRadarScan:
    def test_radar_declares_at_least_three_sources(self):
        """TrendRadarAgent must expose a sources list with >=3 entries."""
        radar = TrendRadarAgent.__dict__
        # Either a class attribute or property; either way the public surface
        # must surface the source list.
        sources_attr = TrendRadarAgent.__dict__.get("sources") or getattr(
            TrendRadarAgent, "sources", None
        )
        # If it's not a class-level constant, the scan() method must mention
        # at least three source names in its implementation.
        import inspect
        src_text = inspect.getsource(TrendRadarAgent)
        distinct_sources = []
        for name in (
            "hackernews",
            "rss_ai_news",
            "apify_hashtags",
            "producthunt",
            "x_trends",
            "youtube_trending",
        ):
            if name in src_text:
                distinct_sources.append(name)
        assert (
            sources_attr is not None and len(sources_attr) >= 3
        ) or len(distinct_sources) >= 3, (
            f"TrendRadarAgent must declare >=3 sources; "
            f"got sources_attr={sources_attr}, found={distinct_sources}"
        )

    def test_scan_writes_trending_topics_to_learnings_json(self, tmp_path: Path):
        """scan() must persist trending_topics into learnings.json."""
        learnings = tmp_path / "learnings.json"
        learnings.write_text(json.dumps({
            "best_hooks": [], "best_times": [], "best_hashtag_sets": [],
            "best_pillars": [], "best_presets": [], "posts": [],
        }))
        cache = tmp_path / "trend_cache.json"
        radar = TrendRadarAgent(
            trend_cache_path=cache, learnings_path=learnings,
        )
        # Replace the scanner with a deterministic stub that yields a known topic
        with patch.object(radar, "_fetch_sources", return_value=[
            {"source": "hackernews", "topic": "Show HN: New LLM router"},
            {"source": "rss_ai_news", "topic": "AI workflow automation"},
            {"source": "apify_hashtags", "topic": "#aisdrs"},
        ]):
            result = radar.scan()

        assert "trending_topics" in result
        assert len(result["trending_topics"]) >= 1
        # Persisted to learnings.json
        loaded = json.loads(learnings.read_text())
        assert "trending_topics" in loaded
        assert isinstance(loaded["trending_topics"], list)
        assert loaded["trending_topics"], "scan() must populate trending_topics"

    def test_scan_failure_does_not_raise(self, tmp_path: Path):
        """If the underlying fetcher throws, scan() returns graceful default."""
        learnings = tmp_path / "learnings.json"
        radar = TrendRadarAgent(
            trend_cache_path=tmp_path / "cache.json",
            learnings_path=learnings,
        )
        with patch.object(radar, "_fetch_sources", side_effect=RuntimeError("network down")):
            result = radar.scan()
        # Must NOT raise; result must still be a dict
        assert isinstance(result, dict)
        # trending_topics may be empty or contain stale data — both acceptable
        assert "trending_topics" in result


# ─── 2. learnings.json schema extension ───────────────────────────────────────


class TestLearningsSchema:
    def test_empty_learnings_has_trending_topics_key(self):
        """GrowthHackerAgent._empty_learnings() must include trending_topics."""
        gh = GrowthHackerAgent(learnings_path=Path("/tmp/nonexistent_learnings_xyz.json"))
        empty = gh._empty_learnings()
        assert "trending_topics" in empty
        assert empty["trending_topics"] == []


# ─── 3. scheduler wires daily_trend_scan at 06:00 UTC ─────────────────────────


class TestSchedulerWiring:
    def test_build_scheduler_registers_daily_trend_scan(self):
        """build_scheduler must register a daily_trend_scan cron at 06:00 UTC."""
        from aeloria import scheduler as sched_mod

        # Provide a settings mock with the interval attrs + a numeric cron hour
        settings = MagicMock()
        settings.worker_interval_minutes = 10
        settings.publish_interval_minutes = 10
        settings.distribution_interval_minutes = 10
        settings.showrunner_interval_minutes = 60
        settings.analytics_interval_minutes = 60
        settings.engagement_interval_minutes = 30
        settings.optimizer_interval_minutes = 1440
        settings.competitor_scrape_interval_minutes = 1440
        settings.newsletter_interval_minutes = 1440

        with patch.object(sched_mod, "AsyncIOScheduler") as MockScheduler:
            mock_sched_inst = MagicMock()
            MockScheduler.return_value = mock_sched_inst
            sched_mod.build_scheduler(
                db=MagicMock(), settings=settings, r2=MagicMock(),
                persona=MagicMock(), ref=MagicMock(), tg=MagicMock(),
                executor=MagicMock(),
            )
        # Look for the daily_trend_scan job registration
        kwargs_list = [c.kwargs for c in mock_sched_inst.add_job.call_args_list]
        ids = [kw.get("id") for kw in kwargs_list]
        assert "daily_trend_scan" in ids, (
            f"build_scheduler must register daily_trend_scan job; got ids={ids}"
        )

        # The matching call should use cron + hour=6, minute=0
        cron_call = next(
            kw for kw in kwargs_list if kw.get("id") == "daily_trend_scan"
        )
        # First positional arg is the trigger name when scheduler.add_job is
        # called like: scheduler.add_job(func, "cron", hour=6, minute=0, id=...)
        call_args = mock_sched_inst.add_job.call_args_list
        call_for_trend = next(
            c for c in call_args if c.kwargs.get("id") == "daily_trend_scan"
        )
        trigger = call_for_trend.args[1] if len(call_for_trend.args) > 1 else call_for_trend.kwargs.get("trigger")
        assert trigger == "cron", (
            f"daily_trend_scan must use cron trigger; got {trigger}"
        )
        # apscheduler CronTrigger accepts hour= and minute= as kwargs
        assert cron_call.get("hour") == 6, (
            f"daily_trend_scan must run at 06:00 UTC; got hour={cron_call.get('hour')}"
        )
        assert cron_call.get("minute") == 0


# ─── 4. MultiAgentPipeline consumes trending_topics ──────────────────────────


class TestPipelineConsumesTrendingTopics:
    def test_get_trending_topic_returns_top_one_from_learnings(self, tmp_path: Path):
        """Pipeline must surface a top-1 trending topic from learnings."""
        from aeloria.generation.multi_agent_pipeline import MultiAgentPipeline

        learnings = tmp_path / "learnings.json"
        learnings.write_text(json.dumps({
            "best_hooks": [], "best_times": [], "best_hashtag_sets": [],
            "best_pillars": [], "best_presets": [], "posts": [],
            "trending_topics": [
                {"topic": "GPT-5 launches", "source": "hackernews", "score": 0.9},
                {"topic": "AI SDR tools", "source": "rss_ai_news", "score": 0.7},
            ],
        }))
        pipeline = MultiAgentPipeline(
            persona_name="young_energetic",
            learnings_path=learnings,
            trend_cache_path=tmp_path / "trend_cache.json",
        )
        topic = pipeline.get_trending_topic()
        assert topic == "GPT-5 launches"

    def test_pipeline_proceeds_when_no_trending_topics(self, tmp_path: Path):
        """If learnings has no trending_topics, pipeline proceeds silently."""
        from aeloria.generation.multi_agent_pipeline import MultiAgentPipeline

        learnings = tmp_path / "learnings.json"
        learnings.write_text(json.dumps({
            "best_hooks": [], "best_times": [], "best_hashtag_sets": [],
            "best_pillars": [], "best_presets": [], "posts": [],
        }))
        pipeline = MultiAgentPipeline(
            persona_name="young_energetic",
            learnings_path=learnings,
            trend_cache_path=tmp_path / "trend_cache.json",
        )
        # Must not raise
        assert pipeline.get_trending_topic() is None