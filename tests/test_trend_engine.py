"""Tests for trend-responsive content engine."""
import pytest
from aeloria.distribution.trend_engine import TrendEngine, TrendSignal


class TestScoreRelevance:
    def setup_method(self):
        self.engine = TrendEngine()

    def test_ai_tool_launch_scores_high(self):
        score, pillar = self.engine._score_relevance("New AI tool launched for workflow automation")
        assert score > 0.5
        assert pillar in ("ai_tools", "ai_workflows")

    def test_non_ai_content_scores_zero(self):
        score, pillar = self.engine._score_relevance("New recipe for chocolate cake")
        assert score == 0.0
        assert pillar == ""

    def test_ai_jobs_content_matches_future_pillar(self):
        score, pillar = self.engine._score_relevance("AI will replace jobs in this industry")
        assert score > 0.0
        assert pillar == "future_of_business"

    def test_case_study_content(self):
        score, pillar = self.engine._score_relevance("AI case study showing 40% savings")
        assert score > 0.0
        assert pillar == "case_studies"


class TestDetermineUrgency:
    def setup_method(self):
        self.engine = TrendEngine()

    def test_high_score_x_is_high_urgency(self):
        assert self.engine._determine_urgency(0.9, "x") == "high"

    def test_high_score_producthunt_is_high(self):
        assert self.engine._determine_urgency(0.85, "producthunt") == "high"

    def test_medium_score_is_normal(self):
        assert self.engine._determine_urgency(0.6, "hackernews") == "normal"

    def test_low_score_is_low(self):
        assert self.engine._determine_urgency(0.3, "google_trends") == "low"


class TestScan:
    def test_scan_with_raw_trends(self):
        engine = TrendEngine()
        engine.min_score = 0.3
        engine.min_score = 0.3
        raw = [
            {"topic": "New AI automation tool", "source": "producthunt", "url": "https://ph.com/123", "description": "Workflow automation with AI"},
            {"topic": "Chocolate cake recipe", "source": "x", "url": "https://x.com/123", "description": "Best cake ever"},
        ]
        signals = engine.scan(raw_trends=raw)
        assert len(signals) == 1  # only the AI one passes
        assert signals[0].topic == "New AI automation tool"
        assert signals[0].pillar != ""

    def test_scan_filters_low_scores(self):
        engine = TrendEngine()
        engine.min_score = 0.8
        raw = [
            {"topic": "AI tool", "source": "x", "description": "A new AI tool for automation"},
        ]
        signals = engine.scan(raw_trends=raw)
        # Score should be < 0.8 for this simple text
        assert len(signals) == 0 or signals[0].score >= 0.8

    def test_scan_sorted_by_score(self):
        engine = TrendEngine()
        engine.min_score = 0.0
        raw = [
            {"topic": "AI automation workflow tool pipeline integration", "source": "x", "description": ""},
            {"topic": "AI tool", "source": "x", "description": ""},
        ]
        signals = engine.scan(raw_trends=raw)
        if len(signals) >= 2:
            assert signals[0].score >= signals[1].score

    def test_scan_empty_input(self):
        engine = TrendEngine()
        signals = engine.scan(raw_trends=[])
        assert signals == []


class TestGenerateReactiveBrief:
    def test_brief_has_id(self):
        engine = TrendEngine()
        trend = TrendSignal(topic="New AI tool", source="producthunt", score=0.8, pillar="ai_tools")
        brief = engine.generate_reactive_brief(trend)
        assert brief["id"]
        assert "trend" in brief["id"]

    def test_brief_has_prompt_seed(self):
        engine = TrendEngine()
        trend = TrendSignal(topic="GPT-5 launch", source="x", score=0.9, pillar="ai_tools")
        brief = engine.generate_reactive_brief(trend)
        assert "Aeloria" in brief["prompt_seed"]
        assert "GPT-5" in brief["prompt_seed"]

    def test_brief_has_pillar(self):
        engine = TrendEngine()
        trend = TrendSignal(topic="AI workflow", source="x", score=0.7, pillar="ai_workflows")
        brief = engine.generate_reactive_brief(trend)
        assert brief["pillar"] == "ai_workflows"

    def test_brief_marked_reactive(self):
        engine = TrendEngine()
        trend = TrendSignal(topic="AI tool", source="x", score=0.7, pillar="ai_tools")
        brief = engine.generate_reactive_brief(trend)
        assert brief["reactive"] is True