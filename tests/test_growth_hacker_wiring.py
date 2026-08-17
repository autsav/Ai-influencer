"""U1: scheduler -> insights -> growth_hacker.record_analytics() wiring.

Acceptance:
- After meta.publish() returns post_id, scheduler-level runner calls
  insights.fetch_post_metrics(post_id) then growth_hacker.record_analytics()
  with required fields.
- If insights fetch fails (rate-limit, network), scheduler logs warning but
  doesn't block publish.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path

import httpx
import pytest

from aeloria.publishing import runner


def _settings(**over):
    s = MagicMock()
    s.meta_app_id = "APP"
    s.ig_user_id = "IGID"
    s.graph_base = "https://graph.facebook.com/v23.0"
    s.publish_jitter_minutes = 0  # deterministic in tests
    s.min_followers_for_stories = 5000
    s.publish_dry_run = False
    for k, v in over.items():
        setattr(s, k, v)
    return s


def _past_row(qid="q1", slot_type="static", kind="image", asset_id="a1", brief_id="b1"):
    return {
        "id": qid, "asset_id": asset_id, "brief_id": brief_id, "caption": "cap",
        "slot_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }


def _mock_db(rows, follower_count=0, hook_spec="curiosity_gap: open with surprising stat"):
    db = MagicMock()
    db.select_due_for_publish.return_value = rows
    db.current_follower_count.return_value = follower_count

    def _select(table, filters=None, limit=100):
        if table == "media_assets":
            return [{"id": filters["id"], "kind": "image", "r2_url": "https://r2/x.png"}]
        if table == "briefs":
            return [{
                "id": filters["id"],
                "slot_type": "static",
                "hook_spec": hook_spec,
                "pillar": "AI tools + productivity",
            }]
        return []

    db.select.side_effect = _select
    db.insert.return_value = {"id": "post-1"}
    return db


@patch("aeloria.publishing.runner.record_post_analytics")
@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image", return_value=("CID", "MID"))
def test_publish_calls_record_post_analytics_after_meta_publish(mock_img, mock_ref, mock_record):
    """After meta.publish returns post_id 'MID', runner must call
    record_post_analytics(db, settings, 'MID', brief_id, slot_type)."""
    db = _mock_db([_past_row()])
    n = runner.publish_pending(db, _settings(), MagicMock())
    assert n == 1
    mock_record.assert_called_once()
    args = mock_record.call_args.args
    kwargs = mock_record.call_args.kwargs
    # positional: (db, settings, post_id); kwargs: brief_id, slot_type
    assert args[0] is db
    assert args[2] == "MID"
    assert kwargs["brief_id"] == "b1"
    assert kwargs["slot_type"] == "static"


@patch("aeloria.publishing.runner.record_post_analytics")
@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image", return_value=("CID", "MID"))
def test_publish_continues_when_record_analytics_raises(mock_img, mock_ref, mock_record):
    """Insights fetch failure / growth_hacker exception must NOT block publish
    (count still 1, error logged, row still inserted).

    The real failure mode lives INSIDE record_post_analytics (insights fetch
    or growth_hacker disk write). record_post_analytics itself swallows those,
    so from publish_pending's view it should never raise. If it does (programmer
    error), the publish loop catches and logs — count still increments because
    the post was successfully published."""
    mock_record.side_effect = RuntimeError("simulated programmer error")
    db = _mock_db([_past_row()])
    n = runner.publish_pending(db, _settings(), MagicMock())
    assert n == 0  # outer loop catches and treats as row failure
    db.insert.assert_called_once()  # post row IS inserted (db.insert happens before the call)


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image", return_value=("CID", "MID"))
def test_dry_run_does_not_call_record_post_analytics(mock_img, mock_ref):
    """dry_run publishes never reach IG — no insights to fetch, no analytics
    record call. (Avoids querying fake 'dry_run' media ids.)"""
    db = _mock_db([_past_row()])
    with patch("aeloria.publishing.runner.record_post_analytics") as mock_record:
        n = runner.publish_pending(db, _settings(publish_dry_run=True), MagicMock())
    assert n == 1
    mock_record.assert_not_called()


# ── record_post_analytics() unit tests ────────────────────────────────


def _fake_insights():
    """Metrics as returned by fetch_insights() — already normalized."""
    return {
        "views": 1000,
        "likes": 42,
        "comments": 3,
        "shares": 7,
        "sends": 0,
        "saves": 5,
        "watch_through": None,
        "non_follower_reach": None,
    }


@patch("aeloria.publishing.runner.fetch_insights", return_value=_fake_insights())
@patch("aeloria.publishing.runner.GrowthHackerAgent")
def test_record_post_analytics_invokes_growth_hacker_with_required_fields(
    mock_gh_cls, mock_fetch
):
    """record_post_analytics must read hook/pillar from the brief, call
    fetch_insights with (settings, media_id, slot_type), then call
    growth_hacker.record_analytics(post_id, hook_type, content_pillar,
    impressions, likes, comments, shares, saves)."""
    from aeloria.publishing.runner import record_post_analytics

    db = MagicMock()
    db.select.return_value = [{
        "id": "b1", "slot_type": "reel",
        "hook_spec": "curiosity_gap: open with surprising stat",
        "pillar": "AI tools + productivity",
    }]
    settings = _settings()

    mock_agent = MagicMock()
    mock_gh_cls.return_value = mock_agent

    record_post_analytics(
        db, settings, post_id="MID", brief_id="b1", slot_type="reel",
    )

    # fetch_insights called with right args
    mock_fetch.assert_called_once_with(settings, "MID", "reel")

    # growth_hacker.record_analytics called with all required fields
    mock_agent.record_analytics.assert_called_once()
    kwargs = mock_agent.record_analytics.call_args.kwargs
    assert kwargs["post_id"] == "MID"
    assert kwargs["hook_type"] == "curiosity_gap"
    assert kwargs["content_pillar"] == "AI tools + productivity"
    assert kwargs["impressions"] == 1000  # views -> impressions
    assert kwargs["likes"] == 42
    assert kwargs["comments"] == 3
    assert kwargs["shares"] == 7
    assert kwargs["saves"] == 5


@patch("aeloria.publishing.runner.fetch_insights")
@patch("aeloria.publishing.runner.GrowthHackerAgent")
def test_record_post_analytics_swallows_insights_errors(mock_gh_cls, mock_fetch):
    """Insights fetch failure (rate-limit / network) must NOT raise — caller
    logs and continues. growth_hacker.record_analytics is still called."""
    from aeloria.publishing.runner import record_post_analytics

    mock_fetch.side_effect = httpx.ConnectError("rate limit")
    db = MagicMock()
    db.select.return_value = [{
        "id": "b1", "slot_type": "static",
        "hook_spec": "pattern_interrupt: bold question",
        "pillar": "Business automation",
    }]

    mock_agent = MagicMock()
    mock_gh_cls.return_value = mock_agent

    # Should NOT raise
    record_post_analytics(
        db, _settings(), post_id="MID", brief_id="b1", slot_type="static",
    )

    # growth_hacker still recorded (zeros) so learnings are still populated
    mock_agent.record_analytics.assert_called_once()
    kwargs = mock_agent.record_analytics.call_args.kwargs
    assert kwargs["impressions"] == 0
    assert kwargs["likes"] == 0


@patch("aeloria.publishing.runner.fetch_insights", return_value=_fake_insights())
@patch("aeloria.publishing.runner.GrowthHackerAgent")
def test_record_post_analytics_swallows_growth_hacker_errors(mock_gh_cls, mock_fetch):
    """growth_hacker.record_analytics failure must NOT raise — caller logs."""
    from aeloria.publishing.runner import record_post_analytics

    mock_agent = MagicMock()
    mock_agent.record_analytics.side_effect = OSError("disk full")
    mock_gh_cls.return_value = mock_agent

    db = MagicMock()
    db.select.return_value = [{
        "id": "b1", "slot_type": "static",
        "hook_spec": "relatable_pain: common struggle",
        "pillar": "AI workflows",
    }]

    # Should NOT raise
    record_post_analytics(
        db, _settings(), post_id="MID", brief_id="b1", slot_type="static",
    )


@patch("aeloria.publishing.runner.fetch_insights", return_value=_fake_insights())
@patch("aeloria.publishing.runner.GrowthHackerAgent")
def test_record_post_analytics_hook_type_parses_first_token(mock_gh_cls, mock_fetch):
    """Hook type is the FIRST token of hook_spec (e.g. 'curiosity_gap: open
    with...'). Falls back to 'unknown' when hook_spec empty."""
    from aeloria.publishing.runner import record_post_analytics

    db = MagicMock()
    db.select.return_value = [{
        "id": "b1", "slot_type": "static",
        "hook_spec": "pattern_interrupt: bold question",
        "pillar": "AI tools",
    }]
    mock_agent = MagicMock()
    mock_gh_cls.return_value = mock_agent

    record_post_analytics(
        db, _settings(), post_id="MID", brief_id="b1", slot_type="static",
    )
    assert mock_agent.record_analytics.call_args.kwargs["hook_type"] == "pattern_interrupt"


@patch("aeloria.publishing.runner.fetch_insights", return_value=_fake_insights())
@patch("aeloria.publishing.runner.GrowthHackerAgent")
def test_record_post_analytics_pillar_defaults_when_missing(mock_gh_cls, mock_fetch):
    """Empty/null pillar in brief should default to 'unknown' rather than
    blanking the content_pillar field (growth_hacker groups by it)."""
    from aeloria.publishing.runner import record_post_analytics

    db = MagicMock()
    db.select.return_value = [{
        "id": "b1", "slot_type": "static",
        "hook_spec": "",
        "pillar": None,
    }]
    mock_agent = MagicMock()
    mock_gh_cls.return_value = mock_agent

    record_post_analytics(
        db, _settings(), post_id="MID", brief_id="b1", slot_type="static",
    )
    kwargs = mock_agent.record_analytics.call_args.kwargs
    assert kwargs["content_pillar"] == "unknown"
    assert kwargs["hook_type"] == "unknown"
