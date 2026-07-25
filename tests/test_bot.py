import threading
from unittest.mock import MagicMock, patch

from aeloria.approval.bot import process_update, run, supervise_bot
from aeloria.approval.handlers import CAPTION_PROMPT_PREFIX


def test_callback_query_dispatch():
    db, tg = MagicMock(), MagicMock()
    u = {"update_id": 1, "callback_query": {"id": "cb1", "data": "approve:q1"}}
    process_update(u, db, tg)
    tg.answer_callback.assert_called_once()
    assert "Approved" in tg.answer_callback.call_args.args[1]
    tg.send_message.assert_not_called()  # toast succeeded -> no message fallback


def test_callback_sends_message_when_toast_stale():
    # answerCallbackQuery 400 (query too old under flaky polling) must not swallow
    # feedback — the operator gets a confirmation message instead.
    db, tg = MagicMock(), MagicMock()
    tg.answer_callback.return_value = False
    u = {"update_id": 1, "callback_query": {"id": "cb1", "data": "approve:q1"}}
    process_update(u, db, tg)
    db.update.assert_called_once()  # the approve still applied
    tg.send_message.assert_called_once()
    assert "Approved" in tg.send_message.call_args.args[0]


def test_caption_callback_sends_force_reply():
    db, tg = MagicMock(), MagicMock()
    u = {"update_id": 2, "callback_query": {"id": "cb2", "data": "caption:q1"}}
    process_update(u, db, tg)
    tg.send_message.assert_called_once_with(f"{CAPTION_PROMPT_PREFIX} q1", force_reply=True)


def test_caption_reply_message():
    db, tg = MagicMock(), MagicMock()
    u = {
        "update_id": 3,
        "message": {
            "text": "cozy new caption",
            "reply_to_message": {"text": f"{CAPTION_PROMPT_PREFIX} q9"},
        },
    }
    process_update(u, db, tg)
    db.update.assert_called_once_with("queue", "q9", {"caption": "cozy new caption"})
    tg.send_message.assert_called_once()


def test_irrelevant_update_ignored():
    db, tg = MagicMock(), MagicMock()
    process_update({"update_id": 4, "message": {"text": "hi"}}, db, tg)
    db.update.assert_not_called()
    tg.send_message.assert_not_called()


def test_run_exits_immediately_when_stop_event_set():
    """stop_event already set → loop body never runs → run returns, no polling."""
    stop = threading.Event()
    stop.set()
    with patch("aeloria.approval.bot.get_settings") as gs, \
         patch("aeloria.approval.bot.Db"), \
         patch("aeloria.approval.bot.Telegram") as MockTg:
        gs.return_value.telegram_bot_token = "t"
        gs.return_value.telegram_chat_id = "c"
        tg = MockTg.return_value
        tg.get_updates.return_value = []
        run(stop)
        tg.get_updates.assert_not_called()


def test_supervise_bot_returns_on_missing_telegram():
    """run() raises SystemExit (telegram not configured) → supervisor returns, no crash."""
    with patch("aeloria.approval.bot.run", side_effect=SystemExit("no telegram")):
        supervise_bot(threading.Event())  # must not raise


@patch("aeloria.approval.bot.time.sleep")
def test_supervise_bot_restarts_after_crash_then_stops(mock_sleep):
    """first run() crashes → supervisor restarts; once 2nd run() is blocking on
    stop.wait, set stop → exits cleanly. Deterministic (no fixed sleeps)."""
    calls = []

    def fake_run(stop):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        stop.wait(timeout=2)  # 2nd invocation blocks until stop set

    with patch("aeloria.approval.bot.run", side_effect=fake_run):
        stop = threading.Event()
        t = threading.Thread(target=supervise_bot, args=(stop,))
        t.start()
        # Wait until the supervisor has restarted into the 2nd run() (now blocking
        # on stop.wait) before signaling stop — otherwise the loop guard exits early.
        for _ in range(200):
            if len(calls) >= 2:
                break
            stop.wait(0.01)  # Event.wait is NOT patched → real ~10ms yields
        stop.set()
        t.join(timeout=3)
        assert len(calls) >= 2
        assert not t.is_alive()


from aeloria.approval.handlers import handle_trend_command


def test_trend_add_inserts_row():
    db = MagicMock()
    db.insert.return_value = {"id": "t1"}
    res = handle_trend_command("/trend add audio forest-ambient | forest ambient rising", db)
    assert "added" in res.lower()
    args = db.insert.call_args.args
    assert args[0] == "trends"
    row = args[1]
    assert row["kind"] == "audio"
    assert row["ref"] == "forest-ambient"
    assert row["note"] == "forest ambient rising"
    assert row["expires_at"] is not None


def test_trend_list_returns_active():
    db = MagicMock()
    db.select.return_value = [
        {"id": "t1", "kind": "audio", "ref": "forest-ambient", "note": "rising",
         "expires_at": "2099-01-01T00:00:00+00:00"},
    ]
    res = handle_trend_command("/trend list", db)
    assert "forest-ambient" in res
    assert "t1" in res  # row id shown so /trend expire <id> is usable


def test_trend_expire_sets_expires_at():
    db = MagicMock()
    res = handle_trend_command("/trend expire t1", db)
    assert "expired" in res.lower()
    db.update.assert_called_once()
    assert db.update.call_args.args[0] == "trends"
    assert db.update.call_args.args[1] == "t1"
    assert db.update.call_args.args[2]["expires_at"] is not None


def test_trend_unknown_returns_help():
    res = handle_trend_command("/trend frobnicate", MagicMock())
    assert "usage" in res.lower() or "unknown" in res.lower()


def test_trend_add_missing_pipe_returns_help():
    res = handle_trend_command("/trend add audio norefnote", MagicMock())
    assert "usage" in res.lower() or "unknown" in res.lower()


def test_bot_routes_trend_command():
    db, tg = MagicMock(), MagicMock()
    db.insert.return_value = {"id": "t1"}
    u = {"update_id": 9, "message": {"text": "/trend add audio x | y"}}
    process_update(u, db, tg)
    tg.send_message.assert_called_once()
    assert db.insert.called


# ---- Chat gating: commands from foreign chats are ignored ----

def test_foreign_chat_command_ignored():
    db, tg = MagicMock(), MagicMock()
    u = {"update_id": 10, "message": {
        "text": "/trend add audio x | y", "chat": {"id": 999}}}
    process_update(u, db, tg, allowed_chat_id="123")
    db.insert.assert_not_called()
    tg.send_message.assert_not_called()


def test_foreign_chat_caption_reply_ignored():
    db, tg = MagicMock(), MagicMock()
    u = {"update_id": 11, "message": {
        "text": "hijacked caption", "chat": {"id": 999},
        "reply_to_message": {"text": f"{CAPTION_PROMPT_PREFIX} q9"}}}
    process_update(u, db, tg, allowed_chat_id="123")
    db.update.assert_not_called()
    tg.send_message.assert_not_called()


def test_matching_chat_int_vs_str_tolerant():
    db, tg = MagicMock(), MagicMock()
    db.insert.return_value = {"id": "t1"}
    u = {"update_id": 12, "message": {
        "text": "/trend add audio x | y", "chat": {"id": 123}}}  # int id
    process_update(u, db, tg, allowed_chat_id="123")             # str setting
    tg.send_message.assert_called_once()
    assert db.insert.called


def test_message_without_chat_ignored_when_gated():
    db, tg = MagicMock(), MagicMock()
    u = {"update_id": 13, "message": {"text": "/trend list"}}
    process_update(u, db, tg, allowed_chat_id="123")
    tg.send_message.assert_not_called()


def test_foreign_chat_callback_ignored():
    db, tg = MagicMock(), MagicMock()
    u = {"update_id": 14, "callback_query": {
        "id": "cb9", "data": "approve:q1",
        "message": {"chat": {"id": 999}}}}
    process_update(u, db, tg, allowed_chat_id="123")
    db.update.assert_not_called()
    tg.answer_callback.assert_not_called()


@patch("aeloria.approval.bot.handle_edit_command", return_value="✏️ edit queued")
def test_edit_command_routed(mock_edit):
    db, tg = MagicMock(), MagicMock()
    u = {"update_id": 1, "message": {"chat": {"id": 123}, "text": "/edit q1 red jacket"}}
    process_update(u, db, tg, allowed_chat_id=123)
    mock_edit.assert_called_once()
    assert mock_edit.call_args.args[0] == "/edit q1 red jacket"
    tg.send_message.assert_called_once_with("✏️ edit queued")
