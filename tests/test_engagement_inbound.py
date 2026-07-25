from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from aeloria.engagement.inbound import poll_inbound


def _settings():
    s = MagicMock()
    s.engagement_recent_days = 3
    return s


def _now_iso(days_ago=0):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


@patch("aeloria.engagement.inbound.draft_reply", return_value="thanks 🌲")
@patch("aeloria.engagement.inbound.fetch_recent_comments")
def test_poll_inbound_drafts_new_comments(mock_fetch, mock_draft):
    posts = [{"id": "p1", "platform_post_id": "mediaA", "published_at": _now_iso(1)}]
    mock_fetch.return_value = [
        {"id": "c1", "text": "love", "username": "u1", "timestamp": ""},
        {"id": "c2", "text": "calm", "username": "u2", "timestamp": ""},
    ]
    db = MagicMock()
    db.select_posts_published_since.return_value = posts
    db.select.return_value = []  # nothing seen yet
    db.insert.side_effect = lambda t, row: {**row, "id": "e1"}
    n = poll_inbound(db, _settings(), MagicMock())
    assert n == 2
    kinds = {c.args[1]["kind"] for c in db.insert.call_args_list}
    assert kinds == {"reply"}
    assert all(c.args[1]["source_id"] in ("c1", "c2") for c in db.insert.call_args_list)


@patch("aeloria.engagement.inbound.draft_reply", return_value="thanks")
@patch("aeloria.engagement.inbound.fetch_recent_comments")
def test_poll_inbound_skips_comments_older_than_window(mock_fetch, mock_draft):
    # A fresh comment (in window) and a stale one (10 days old, outside the
    # 3-day window) — only the fresh one is drafted.
    fresh = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    stale = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S+0000")
    mock_fetch.return_value = [
        {"id": "c_fresh", "text": "hi", "username": "u", "timestamp": fresh},
        {"id": "c_stale", "text": "old", "username": "u", "timestamp": stale},
    ]
    db = MagicMock()
    db.select_posts_published_since.return_value = [
        {"id": "p1", "platform_post_id": "mediaA", "published_at": _now_iso(1)}]
    db.select.return_value = []
    db.insert.side_effect = lambda t, row: {**row, "id": "e"}
    n = poll_inbound(db, _settings(), MagicMock())
    assert n == 1
    assert db.insert.call_args.args[1]["source_id"] == "c_fresh"


@patch("aeloria.engagement.inbound.draft_reply", return_value="thanks")
@patch("aeloria.engagement.inbound.fetch_recent_comments")
def test_poll_inbound_dedups_seen_comments(mock_fetch, mock_draft):
    mock_fetch.return_value = [{"id": "c1", "text": "hi", "username": "u", "timestamp": ""}]
    db = MagicMock()
    db.select_posts_published_since.return_value = [
        {"id": "p1", "platform_post_id": "mediaA", "published_at": _now_iso(1)}]
    db.select.return_value = [{"id": "existing"}]  # c1 already drafted
    n = poll_inbound(db, _settings(), MagicMock())
    assert n == 0
    db.insert.assert_not_called()


@patch("aeloria.engagement.inbound.draft_reply", side_effect=Exception("boom"))
@patch("aeloria.engagement.inbound.fetch_recent_comments")
def test_poll_inbound_isolates_draft_failure(mock_fetch, mock_draft):
    mock_fetch.return_value = [{"id": "c1", "text": "hi", "username": "u", "timestamp": ""}]
    db = MagicMock()
    db.select_posts_published_since.return_value = [
        {"id": "p1", "platform_post_id": "mediaA", "published_at": _now_iso(1)}]
    db.select.return_value = []
    n = poll_inbound(db, _settings(), MagicMock())  # must not raise
    assert n == 0
