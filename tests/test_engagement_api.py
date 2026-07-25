from unittest.mock import MagicMock, patch

import httpx
import pytest

from aeloria.engagement.api import (
    fetch_recent_comments, reply_to_comment, send_dm, EngagementApiError,
)


def _settings():
    s = MagicMock()
    s.graph_base = "https://graph.facebook.com/v23.0"
    s.ig_user_id = "IG"
    return s


def _resp(status, json=None, text=None):
    req = httpx.Request("GET", "https://graph.facebook.com/x")
    if json is not None:
        return httpx.Response(status, json=json, request=req)
    return httpx.Response(status, text=text or "", request=req)


@patch("aeloria.engagement.api.token_store")
@patch("aeloria.engagement.api.httpx.Client")
def test_fetch_recent_comments_normalizes(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    payload = {"data": [
        {"id": "c1", "text": "love this", "username": "fan1", "timestamp": "2026-07-20T10:00:00+0000"},
        {"id": "c2", "text": "so calm", "username": "fan2", "timestamp": "2026-07-20T11:00:00+0000"},
    ]}
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(200, json=payload)
    out = fetch_recent_comments(_settings(), "media-1")
    assert [c["id"] for c in out] == ["c1", "c2"]
    assert out[0]["text"] == "love this" and out[0]["username"] == "fan1"


@patch("aeloria.engagement.api.token_store")
@patch("aeloria.engagement.api.httpx.Client")
def test_reply_to_comment_posts_and_returns_id(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    post = mock_client_cls.return_value.__enter__.return_value.post
    post.return_value = _resp(200, json={"id": "reply-9"})
    rid = reply_to_comment(_settings(), "c1", "thank you 🌲")
    assert rid == "reply-9"
    call = post.call_args
    assert call.args[0].endswith("/c1/replies")
    assert call.kwargs["data"]["message"] == "thank you 🌲"
    assert call.kwargs["data"]["access_token"] == "tok"


@patch("aeloria.engagement.api.token_store")
@patch("aeloria.engagement.api.httpx.Client")
def test_send_dm_posts_recipient_and_message(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    post = mock_client_cls.return_value.__enter__.return_value.post
    post.return_value = _resp(200, json={"message_id": "m-7"})
    mid = send_dm(_settings(), "user-42", "hey, thanks for the follow")
    assert mid == "m-7"
    call = post.call_args
    assert call.args[0].endswith("/IG/messages")
    assert call.kwargs["params"]["access_token"] == "tok"
    assert call.kwargs["json"]["recipient"] == {"id": "user-42"}
    assert call.kwargs["json"]["message"] == {"text": "hey, thanks for the follow"}
    assert "access_token" not in call.kwargs["json"]


@patch("aeloria.engagement.api.token_store")
@patch("aeloria.engagement.api.httpx.Client")
def test_400_raises_engagement_error(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(400, text="bad")
    with pytest.raises(EngagementApiError):
        fetch_recent_comments(_settings(), "media-1")
