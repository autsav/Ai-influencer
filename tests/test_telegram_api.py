from unittest.mock import MagicMock, patch

import pytest

from aeloria.approval.telegram_api import Telegram, TelegramError


def _resp(ok=True, result=None):
    r = MagicMock()
    r.json.return_value = {"ok": ok, "result": result if result is not None else {}}
    r.raise_for_status = MagicMock()
    return r


@patch("aeloria.approval.telegram_api.httpx.post")
def test_send_photo_builds_keyboard(mock_post):
    mock_post.return_value = _resp(result={"message_id": 5})
    tg = Telegram("tok", "chat1")
    out = tg.send_photo("https://x/img.png", "cap", [[("✅", "approve:1"), ("❌", "reject:1")]])
    assert out == {"message_id": 5}
    url = mock_post.call_args.args[0]
    assert url == "https://api.telegram.org/bottok/sendPhoto"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["chat_id"] == "chat1"
    assert payload["reply_markup"]["inline_keyboard"][0][0] == {
        "text": "✅", "callback_data": "approve:1"
    }


@patch("aeloria.approval.telegram_api.httpx.post")
def test_get_updates_passes_offset(mock_post):
    mock_post.return_value = _resp(result=[{"update_id": 7}])
    tg = Telegram("tok", "chat1")
    ups = tg.get_updates(offset=7)
    assert ups == [{"update_id": 7}]
    assert mock_post.call_args.kwargs["json"]["offset"] == 7


@patch("aeloria.approval.telegram_api.httpx.post")
def test_api_not_ok_raises(mock_post):
    mock_post.return_value = _resp(ok=False)
    with pytest.raises(TelegramError):
        Telegram("tok", "chat1").send_message("hi")


def test_send_photo_truncates_caption_to_telegram_limit():
    from unittest.mock import patch, MagicMock
    from aeloria.approval.telegram_api import Telegram, TELEGRAM_CAPTION_LIMIT
    tg = Telegram("tok", "chat")
    with patch("aeloria.approval.telegram_api.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(), json=lambda: {"ok": True, "result": {}})
        tg.send_photo("https://r2/x.png", "x" * 1500, [[("A", "a:{qid}")]])
    sent = mock_post.call_args.kwargs["json"]
    assert len(sent["caption"]) <= TELEGRAM_CAPTION_LIMIT
    assert sent["caption"].endswith("…")
    with patch("aeloria.approval.telegram_api.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(
            raise_for_status=MagicMock(), json=lambda: {"ok": True, "result": {}})
        tg.send_photo("https://r2/x.png", "short", [[("A", "a")]])
    assert mock_post.call_args.kwargs["json"]["caption"] == "short"
