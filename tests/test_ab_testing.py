"""Tests for A/B testing framework."""
import pytest
from aeloria.distribution.ab_testing import (
    ABTest,
    ABTestResult,
    create_test,
    score_test,
    ChampionChallenger,
    _engagement_rate,
)


class TestCreateTest:
    def test_creates_with_id(self):
        brief_a = {"prompt_seed": "curiosity hook"}
        brief_b = {"prompt_seed": "contrarian hook"}
        test = create_test(brief_a, brief_b, pillar="ai_tools")
        assert test.test_id  # non-empty
        assert test.brief_a == brief_a
        assert test.brief_b == brief_b
        assert test.pillar == "ai_tools"
        assert test.status == "pending"
        assert test.winner is None

    def test_unique_ids(self):
        t1 = create_test({"a": 1}, {"b": 2})
        t2 = create_test({"a": 1}, {"b": 2})
        assert t1.test_id != t2.test_id  # different timestamps


class TestEngagementRate:
    def test_basic(self):
        metrics = {"likes": 10, "comments": 5, "shares": 2, "saves": 3, "reach": 100}
        assert _engagement_rate(metrics) == pytest.approx(0.20)

    def test_zero_reach(self):
        assert _engagement_rate({"reach": 0}) == 0.0


class TestScoreTest:
    def test_a_wins(self):
        test = create_test({"hook": "A"}, {"hook": "B"})
        metrics_a = {"likes": 20, "comments": 5, "shares": 5, "saves": 10, "reach": 100}
        metrics_b = {"likes": 10, "comments": 2, "shares": 1, "saves": 2, "reach": 100}
        result = score_test(test, metrics_a, metrics_b)
        assert result.winner == "A"
        assert result.lift > 0
        assert test.winner == "A"
        assert test.status == "completed"

    def test_b_wins(self):
        test = create_test({"hook": "A"}, {"hook": "B"})
        metrics_a = {"likes": 5, "comments": 1, "reach": 100}
        metrics_b = {"likes": 20, "comments": 10, "shares": 5, "saves": 5, "reach": 100}
        result = score_test(test, metrics_a, metrics_b)
        assert result.winner == "B"

    def test_tie_when_lift_too_small(self):
        test = create_test({"hook": "A"}, {"hook": "B"})
        metrics_a = {"likes": 10, "reach": 100}  # 0.10
        metrics_b = {"likes": 11, "reach": 100}  # 0.11 — 10% lift, but min_lift=0.05
        result = score_test(test, metrics_a, metrics_b, min_lift=0.20)  # require 20%
        assert result.winner == "tie"

    def test_tie_when_equal(self):
        test = create_test({"hook": "A"}, {"hook": "B"})
        metrics_a = {"likes": 10, "reach": 100}
        metrics_b = {"likes": 10, "reach": 100}
        result = score_test(test, metrics_a, metrics_b)
        assert result.winner == "tie"
        assert result.lift == 0.0

    def test_insufficient_reach_declares_tie(self):
        test = create_test({"hook": "A"}, {"hook": "B"})
        metrics_a = {"likes": 20, "reach": 10}  # below min_reach
        metrics_b = {"likes": 5, "reach": 200}
        result = score_test(test, metrics_a, metrics_b, min_reach=50)
        assert result.winner == "tie"


class TestChampionChallenger:
    def test_first_variant_becomes_champion(self):
        cc = ChampionChallenger()
        brief = {"hook": "first"}
        metrics = {"likes": 10, "reach": 100}
        result = cc.challenge(brief, metrics)
        assert result is None  # no test run, just set champion
        assert cc.champion == brief
        assert cc.champion_rate == pytest.approx(0.10)

    def test_challenger_loses(self):
        cc = ChampionChallenger()
        cc.champion = {"hook": "champ"}
        cc.champion_rate = 0.20
        challenger_brief = {"hook": "weak"}
        challenger_metrics = {"likes": 5, "reach": 100}  # 0.05 — much worse
        result = cc.challenge(challenger_brief, challenger_metrics)
        assert result.winner == "A"  # champion wins
        assert cc.champion == {"hook": "champ"}  # unchanged

    def test_challenger_wins(self):
        cc = ChampionChallenger(min_lift=0.05)
        cc.champion = {"hook": "champ"}
        cc.champion_rate = 0.10
        challenger_brief = {"hook": "strong"}
        challenger_metrics = {"likes": 20, "comments": 5, "shares": 5, "saves": 10, "reach": 100}
        # challenger rate = 0.40, champion rate = 0.10
        # The champion metrics are synthetic in challenge() — uses engagement key
        result = cc.challenge(challenger_brief, challenger_metrics)
        assert result.winner == "B"  # challenger wins
        assert cc.champion == challenger_brief  # new champion

    def test_history_recorded(self):
        cc = ChampionChallenger()
        cc.champion = {"hook": "champ"}
        cc.champion_rate = 0.10
        cc.challenge({"hook": "challenger"}, {"likes": 15, "reach": 100})
        assert len(cc.history) == 1