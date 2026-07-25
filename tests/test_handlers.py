from unittest.mock import MagicMock

from aeloria.approval.handlers import (
    CAPTION_PROMPT_PREFIX,
    handle_callback,
    handle_caption_reply,
)


def test_approve_updates_queue():
    db = MagicMock()
    ack, followup = handle_callback("approve:q1", db)
    db.update.assert_called_once_with("queue", "q1", {"approval": "approved"})
    assert "Approved" in ack and followup is None


def test_reject_sets_reason():
    db = MagicMock()
    ack, _ = handle_callback("reject:q1", db)
    db.update.assert_called_once_with(
        "queue", "q1", {"approval": "rejected", "reject_reason": "manual reject"}
    )
    assert "Rejected" in ack


def test_regen_resets_brief():
    db = MagicMock()
    db.select.return_value = [{"id": "q1", "brief_id": "b1"}]
    ack, _ = handle_callback("regen:q1", db)
    db.update.assert_any_call(
        "queue", "q1", {"approval": "rejected", "reject_reason": "regen requested"}
    )
    db.update.assert_any_call("briefs", "b1", {"status": "planned"})
    assert "Regen" in ack


def test_caption_returns_followup_prompt():
    db = MagicMock()
    ack, followup = handle_callback("caption:q1", db)
    db.update.assert_not_called()
    assert followup == f"{CAPTION_PROMPT_PREFIX} q1"


def test_caption_reply_updates_queue():
    db = MagicMock()
    res = handle_caption_reply(f"{CAPTION_PROMPT_PREFIX} q1", "new caption", db)
    db.update.assert_called_once_with("queue", "q1", {"caption": "new caption"})
    assert res != ""


def test_caption_reply_ignores_other_messages():
    db = MagicMock()
    assert handle_caption_reply("random text", "x", db) == ""
    db.update.assert_not_called()


def test_unknown_action():
    ack, followup = handle_callback("dance:q1", MagicMock())
    assert "unknown" in ack.lower() and followup is None


def test_engagement_approve_reject_callbacks():
    db = MagicMock()
    ack, follow = handle_callback("engapprove:e1", db)
    assert "Approved" in ack and follow is None
    db.update.assert_called_with("engagements", "e1", {"approval": "approved"})
    ack2, _ = handle_callback("engreject:e2", db)
    assert "Rejected" in ack2
    db.update.assert_called_with("engagements", "e2", {"approval": "rejected"})
