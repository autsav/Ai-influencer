"""A/B testing framework for content optimization.

Generate 2 variants (different hooks/images). Publish variant A to the first
audience window, B to the second. Score the winner based on engagement rate.
Rotate the champion into future content.

Usage:
    from aeloria.distribution.ab_testing import ABTest, ABTestResult, create_test
    test = create_test(brief_a, brief_b, pillar="ai_tools")
    # ... generate both variants, publish A then B ...
    result = test.score(winner_metrics_a, winner_metrics_b)
"""
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass
class ABTest:
    """An A/B test comparing two content variants."""
    test_id: str
    brief_a: dict
    brief_b: dict
    pillar: str
    created_at: str = ""
    status: str = "pending"  # pending → running → completed
    variant_a_id: str | None = None
    variant_b_id: str | None = None
    winner: str | None = None  # "A", "B", or "tie"

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.test_id:
            self.test_id = hashlib.md5(
                f"{self.pillar}-{self.created_at}".encode()
            ).hexdigest()[:12]


@dataclass
class ABTestResult:
    """Result of scoring an A/B test."""
    test_id: str
    winner: str  # "A", "B", or "tie"
    engagement_rate_a: float
    engagement_rate_b: float
    lift: float  # percentage improvement of winner over loser
    metrics_a: dict = field(default_factory=dict)
    metrics_b: dict = field(default_factory=dict)

    def __repr__(self):
        return (
            f"ABTestResult(winner={self.winner}, "
            f"A={self.engagement_rate_a:.4f}, B={self.engagement_rate_b:.4f}, "
            f"lift={self.lift:+.1%})"
        )


def create_test(brief_a: dict, brief_b: dict, pillar: str = "") -> ABTest:
    """Create a new A/B test with two content variants.

    Args:
        brief_a: First variant brief (e.g., curiosity hook)
        brief_b: Second variant brief (e.g., contrarian hook)
        pillar: Content pillar for tracking

    Returns:
        ABTest instance with generated test_id
    """
    return ABTest(
        test_id="",
        brief_a=brief_a,
        brief_b=brief_b,
        pillar=pillar,
    )


def _engagement_rate(metrics: dict) -> float:
    """Calculate engagement rate from metrics dict."""
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


def score_test(
    test: ABTest,
    metrics_a: dict,
    metrics_b: dict,
    min_reach: int = 50,
    min_lift: float = 0.05,
) -> ABTestResult:
    """Score an A/B test by comparing engagement rates.

    Args:
        test: The ABTest to score
        metrics_a: Performance metrics for variant A
        metrics_b: Performance metrics for variant B
        min_reach: Minimum reach for a variant to be eligible (avoid small-sample noise)
        min_lift: Minimum lift percentage to declare a winner (avoid statistical ties)

    Returns:
        ABTestResult with winner and lift
    """
    rate_a = _engagement_rate(metrics_a)
    rate_b = _engagement_rate(metrics_b)

    # Check minimum reach
    if metrics_a.get("reach", 0) < min_reach or metrics_b.get("reach", 0) < min_reach:
        log.info("A/B test %s: insufficient reach, declaring tie", test.test_id)
        return ABTestResult(
            test_id=test.test_id,
            winner="tie",
            engagement_rate_a=rate_a,
            engagement_rate_b=rate_b,
            lift=0.0,
            metrics_a=metrics_a,
            metrics_b=metrics_b,
        )

    # Calculate lift
    if rate_a > rate_b:
        base = rate_b if rate_b > 0 else 0.001
        lift = (rate_a - base) / base
        winner = "A" if lift >= min_lift else "tie"
    elif rate_b > rate_a:
        base = rate_a if rate_a > 0 else 0.001
        lift = (rate_b - base) / base
        winner = "B" if lift >= min_lift else "tie"
    else:
        lift = 0.0
        winner = "tie"

    test.winner = winner
    test.status = "completed"

    result = ABTestResult(
        test_id=test.test_id,
        winner=winner,
        engagement_rate_a=rate_a,
        engagement_rate_b=rate_b,
        lift=lift,
        metrics_a=metrics_a,
        metrics_b=metrics_b,
    )

    log.info(
        "A/B test %s scored: winner=%s, A=%.4f, B=%.4f, lift=%+.1f%%",
        test.test_id, winner, rate_a, rate_b, lift,
    )

    return result


class ChampionChallenger:
    """Manages a rotating champion/challenger system.

    The current best-performing variant (champion) is kept until a challenger
    beats it by a significant margin. This enables continuous optimization.
    """

    def __init__(self, min_lift: float = 0.10):
        self.champion: dict | None = None
        self.champion_rate: float = 0.0
        self.min_lift = min_lift
        self.history: list[ABTestResult] = []

    def challenge(self, challenger_brief: dict, challenger_metrics: dict) -> ABTestResult | None:
        """Challenge the current champion with a new variant.

        If the challenger wins by >= min_lift, it becomes the new champion.
        Returns the test result, or None if no champion exists yet.
        """
        if self.champion is None:
            # First variant becomes champion by default
            self.champion = challenger_brief
            self.champion_rate = _engagement_rate(challenger_metrics)
            log.info("Champion set: rate=%.4f", self.champion_rate)
            return None

        test = create_test(self.champion, challenger_brief)
        # Synthesize champion metrics from stored rate
        champ_engagement = int(self.champion_rate * 100)
        champ_metrics = {"likes": champ_engagement, "comments": 0, "shares": 0, "saves": 0, "reach": 100}
        result = score_test(test, champ_metrics, challenger_metrics)

        self.history.append(result)

        if result.winner == "B":
            self.champion = challenger_brief
            self.champion_rate = result.engagement_rate_b
            log.info("New champion! rate=%.4f (was %.4f)", self.champion_rate, result.engagement_rate_a)

        return result