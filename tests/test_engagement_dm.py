from unittest.mock import MagicMock, patch

from aeloria.engagement.dm import poll_dms


@patch("aeloria.engagement.dm.draft_reply", return_value="hey, thank you 🌿")
@patch("aeloria.engagement.dm.fetch_dm_conversations")
def test_poll_dms_drafts_new_messages(mock_fetch, mock_draft):
    mock_fetch.return_value = [
        {"id": "conv1", "message_id": "m1", "text": "hi!", "sender_id": "u1"},
        {"id": "conv2", "message_id": "m2", "text": "love your posts", "sender_id": "u2"},
    ]
    db = MagicMock()
    db.select.return_value = []
    db.insert.side_effect = lambda t, row: {**row, "id": "e"}
    n = poll_dms(db, MagicMock(), MagicMock())
    assert n == 2
    rows = [c.args[1] for c in db.insert.call_args_list]
    assert all(r["kind"] == "dm" for r in rows)
    assert {r["source_id"] for r in rows} == {"m1", "m2"}
    assert {r["target"] for r in rows} == {"u1", "u2"}


@patch("aeloria.engagement.dm.draft_reply", return_value="x")
@patch("aeloria.engagement.dm.fetch_dm_conversations")
def test_poll_dms_dedups(mock_fetch, mock_draft):
    mock_fetch.return_value = [{"id": "c1", "message_id": "m1", "text": "hi", "sender_id": "u1"}]
    db = MagicMock()
    db.select.return_value = [{"id": "seen"}]
    n = poll_dms(db, MagicMock(), MagicMock())
    assert n == 0
    db.insert.assert_not_called()
