from unittest.mock import MagicMock, patch

from aeloria.optimizer.memo import milestone_reached, reject_reasons, write_memo


def test_milestone_reached_thresholds():
    assert milestone_reached(60000) == "50k"
    assert milestone_reached(12000) == "10k"
    assert milestone_reached(2500) == "2k"
    assert milestone_reached(500) is None


def test_reject_reasons_collects_nonempty_from_queue():
    db = MagicMock()
    db.select_all.return_value = [
        {"approval": "rejected", "reject_reason": "off-brand"},
        {"approval": "approved", "reject_reason": None},
        {"approval": "rejected", "reject_reason": ""},
        {"approval": "rejected", "reject_reason": "  too salesy  "},
    ]
    out = reject_reasons(db)
    assert "off-brand" in out
    assert "too salesy" in out
    assert "" not in out
    db.select_all.assert_called_once_with("queue")


def _settings():
    s = MagicMock()
    return s


@patch("aeloria.optimizer.memo.llm_generate")
def test_write_memo_returns_text_and_sends(mock_llm):
    mock_llm.return_value = "This week: carousels won on saves. Double down."
    db = MagicMock()
    db.current_follower_count.return_value = 2500
    db.select_all.return_value = []
    tg = MagicMock()
    scores = {"n_posts": 20, "dimensions": {"content_format": {"carousel": {"lift": 2.1, "n": 6}}}}
    out = write_memo(db, _settings(), scores, tg=tg)
    assert "carousels won" in out
    tg.send_message.assert_called_once()