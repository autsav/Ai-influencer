from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from aeloria.optimizer.score import _DIMENSIONS, engagement_score, median, score_recent, tier_weights


def test_tier_weights_picks_highest_tier_leq_followers():
    from aeloria.config import get_settings
    tiers = get_settings().optimizer_north_star_tiers
    assert tier_weights(0, tiers)["saves"] == 3 and tier_weights(0, tiers)["likes"] == 0
    assert tier_weights(50000, tiers)["comments"] == 2


def test_engagement_score_is_weighted():
    w = {"reach": 2, "saves": 3, "shares": 3, "comments": 1, "likes": 0}
    m = {"reach": 10, "saves": 4, "shares": 2, "comments": 5, "likes": 100}
    assert engagement_score(m, w) == 2 * 10 + 3 * 4 + 3 * 2 + 1 * 5 + 0 * 100  # likes ignored at tier 0


def test_engagement_score_missing_fields_default_zero():
    w = {"reach": 2, "saves": 3, "shares": 3, "comments": 1, "likes": 0}
    assert engagement_score({"saves": 3}, w) == 9
    assert engagement_score({"saves": None}, w) == 0


def test_median():
    assert median([]) == 0.0
    assert median([5]) == 5.0
    assert median([1, 3]) == 2.0
    assert median([1, 2, 3]) == 2.0


def test_score_recent_covers_new_dimensions():
    for d in ("activity_category", "style_hint", "story_thread", "emotional_beat"):
        assert d in _DIMENSIONS


def _iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _settings():
    s = MagicMock()
    s.optimizer_baseline_days = 14
    from aeloria.config import get_settings
    s.optimizer_north_star_tiers = get_settings().optimizer_north_star_tiers
    return s


def test_score_recent_computes_lift_per_dimension():
    posts = [
        {"id": "p1", "brief_id": "b1", "platform_post_id": "m1", "published_at": _iso(1)},
        {"id": "p2", "brief_id": "b2", "platform_post_id": "m2", "published_at": _iso(2)},
        {"id": "p3", "brief_id": "b3", "platform_post_id": "m3", "published_at": _iso(3)},
    ]
    briefs = {
        "b1": {"id": "b1", "content_format": "carousel", "cta_kind": "save", "series": "cozy-guide"},
        "b2": {"id": "b2", "content_format": "reel", "cta_kind": "comment", "series": "forest-mornings"},
        "b3": {"id": "b3", "content_format": "reel", "cta_kind": "comment", "series": "forest-mornings"},
    }
    # tier-0 weights (followers=0 default): reach=2, saves=3, shares=3, comments=1, likes=0
    metric_rows = [
        {"post_id": "p1", "captured_at": _iso(1), "reach": 10, "saves": 4, "shares": 0, "comments": 0, "likes": 100},  # score 2*10+3*4 = 32
        {"post_id": "p2", "captured_at": _iso(2), "reach": 5, "saves": 0, "shares": 1, "comments": 2, "likes": 50},    # score 2*5+3*1+1*2 = 15
        {"post_id": "p3", "captured_at": _iso(3), "reach": 8, "saves": 2, "shares": 0, "comments": 0, "likes": 20},   # score 2*8+3*2 = 22
    ]
    db = MagicMock()
    db.select_posts_published_since.return_value = posts
    db.select_all.return_value = list(briefs.values())
    db.select_metrics_for_posts.return_value = metric_rows
    out = score_recent(db, _settings())
    assert out["n_posts"] == 3
    # overall median of [32,15,22] = 22
    assert out["overall_median"] == 22.0
    fmt = out["dimensions"]["content_format"]
    assert fmt["carousel"]["n"] == 1 and fmt["carousel"]["lift"] == 32.0 / 22.0
    assert fmt["reel"]["n"] == 2 and fmt["reel"]["lift"] == 18.5 / 22.0  # median[15,22]=18.5


def test_score_recent_empty_returns_zero():
    db = MagicMock()
    db.select_posts_published_since.return_value = []
    out = score_recent(db, _settings())
    assert out["n_posts"] == 0 and out["dimensions"] == {}
    db.select_metrics_for_posts.assert_not_called()


def test_score_recent_uses_latest_metric_per_post():
    posts = [
        {"id": "p1", "brief_id": "b1", "platform_post_id": "m1", "published_at": _iso(1)},
    ]
    briefs = {
        "b1": {"id": "b1", "content_format": "carousel", "cta_kind": "save", "series": "cozy-guide"},
    }
    metric_rows = [
        {"post_id": "p1", "captured_at": _iso(3), "reach": 1, "saves": 0, "shares": 0, "comments": 0, "likes": 5},   # older, score 2
        {"post_id": "p1", "captured_at": _iso(1), "reach": 10, "saves": 4, "shares": 0, "comments": 0, "likes": 40},  # latest, score 32
    ]
    db = MagicMock()
    db.select_posts_published_since.return_value = posts
    db.select_all.return_value = list(briefs.values())
    db.select_metrics_for_posts.return_value = metric_rows
    out = score_recent(db, _settings())
    assert out["n_posts"] == 1
    assert out["overall_median"] == 32.0


def test_score_recent_uses_followers_for_tier_weights():
    # at 50000 followers, likes gets weight 1 instead of 0 (tier-2 weights)
    posts = [{"id": "p1", "brief_id": "b1", "platform_post_id": "m1", "published_at": _iso(1)}]
    briefs = {"b1": {"id": "b1", "content_format": "reel", "cta_kind": "save", "series": "cozy-guide"}}
    metric_rows = [{"post_id": "p1", "captured_at": _iso(1), "reach": 0, "saves": 0, "shares": 0, "comments": 0, "likes": 10}]
    db = MagicMock()
    db.select_posts_published_since.return_value = posts
    db.select_all.return_value = list(briefs.values())
    db.select_metrics_for_posts.return_value = metric_rows
    out = score_recent(db, _settings(), followers=50000)
    assert out["overall_median"] == 10.0  # likes weight=1 at tier-2 -> 1*10
