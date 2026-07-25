from unittest.mock import MagicMock, patch

from aeloria.engagement.outbound import poll_outbound


def _settings():
    s = MagicMock()
    s.engagement_outbound_daily_cap = 2
    return s


def _persona():
    p = MagicMock()
    # persona.niches is a pydantic Niches model with a .core str attribute
    p.niches.core = "wellness + nature (slow living, forest life)"
    return p


@patch("aeloria.engagement.outbound.draft_reply", return_value="this is stunning 🌲")
@patch("aeloria.engagement.outbound.fetch_target_recent_media")
@patch("aeloria.engagement.outbound.collabs")
def test_poll_outbound_drafts_up_to_cap(mock_collabs, mock_fetch, mock_draft):
    mock_collabs.load.return_value = [{"handle": "a"}, {"handle": "b"}, {"handle": "c"}]
    mock_collabs.match.return_value = [
        {"handle": "forestcreator", "niches": ["wellness"]},
        {"handle": "slowliving2", "niches": ["wellness"]},
        {"handle": "third", "niches": ["wellness"]},
    ]
    mock_fetch.side_effect = lambda s, u: [{"id": f"{u}-m", "caption": "hi", "permalink": f"http://{u}"}]
    db = MagicMock()
    db.select.return_value = []
    db.count_engagements_today.return_value = 0  # full daily cap still available
    db.insert.side_effect = lambda t, row: {**row, "id": "e"}
    n = poll_outbound(db, _settings(), _persona())
    assert n == 2  # capped
    rows = [c.args[1] for c in db.insert.call_args_list]
    assert all(r["kind"] == "comment_out" for r in rows)


@patch("aeloria.engagement.outbound.draft_reply", return_value="x")
@patch("aeloria.engagement.outbound.fetch_target_recent_media")
@patch("aeloria.engagement.outbound.collabs")
def test_poll_outbound_dedups_seen_media(mock_collabs, mock_fetch, mock_draft):
    mock_collabs.match.return_value = [{"handle": "forestcreator", "niches": ["wellness"]}]
    mock_fetch.return_value = [{"id": "m1", "caption": "hi", "permalink": "http://x"}]
    db = MagicMock()
    db.select.return_value = [{"id": "seen"}]  # m1 already commented
    db.count_engagements_today.return_value = 0
    n = poll_outbound(db, _settings(), _persona())
    assert n == 0
    db.insert.assert_not_called()


@patch("aeloria.engagement.outbound.draft_reply", return_value="this is stunning 🌲")
@patch("aeloria.engagement.outbound.fetch_target_recent_media")
@patch("aeloria.engagement.outbound.collabs")
def test_poll_outbound_respects_daily_cap_already_used(mock_collabs, mock_fetch, mock_draft):
    """engagement_outbound_daily_cap=2, but 1 comment_out already posted today
    (e.g. by an earlier tick) — only 1 more should draft this round, not 2."""
    mock_collabs.load.return_value = [{"handle": "a"}, {"handle": "b"}, {"handle": "c"}]
    mock_collabs.match.return_value = [
        {"handle": "forestcreator", "niches": ["wellness"]},
        {"handle": "slowliving2", "niches": ["wellness"]},
        {"handle": "third", "niches": ["wellness"]},
    ]
    mock_fetch.side_effect = lambda s, u: [{"id": f"{u}-m", "caption": "hi", "permalink": f"http://{u}"}]
    db = MagicMock()
    db.select.return_value = []
    db.count_engagements_today.return_value = 1  # 1 already posted today
    db.insert.side_effect = lambda t, row: {**row, "id": "e"}
    n = poll_outbound(db, _settings(), _persona())
    assert n == 1  # remaining = cap(2) - already(1) = 1


@patch("aeloria.engagement.outbound.draft_reply", return_value="x")
@patch("aeloria.engagement.outbound.fetch_target_recent_media")
@patch("aeloria.engagement.outbound.collabs")
def test_poll_outbound_no_remaining_cap_skips_entirely(mock_collabs, mock_fetch, mock_draft):
    db = MagicMock()
    db.count_engagements_today.return_value = 2  # already at/over the daily cap
    n = poll_outbound(db, _settings(), _persona())
    assert n == 0
    mock_collabs.load.assert_not_called()
    mock_fetch.assert_not_called()
    db.insert.assert_not_called()
