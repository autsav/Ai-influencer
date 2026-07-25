from unittest.mock import patch

import httpx
import pytest

from aeloria.analytics.followers import FollowersError, fetch_followers


def _settings():
    s = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    s.graph_base = "https://graph.facebook.com/v23.0"
    s.ig_user_id = "ig-123"
    return s


def _resp(status, json=None, text=None):
    req = httpx.Request("GET", "https://graph.facebook.com/x")
    if json is not None:
        return httpx.Response(status, json=json, request=req)
    return httpx.Response(status, text=text or "", request=req)


@patch("aeloria.analytics.followers.token_store")
@patch("aeloria.analytics.followers.httpx.Client")
def test_fetch_followers_returns_count(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(
        200, json={"followers_count": 4321}
    )
    assert fetch_followers(_settings()) == 4321


@patch("aeloria.analytics.followers.token_store")
@patch("aeloria.analytics.followers.httpx.Client")
def test_fetch_followers_request_url_and_token(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(
        200, json={"followers_count": 0}
    )
    fetch_followers(_settings())
    call = mock_client_cls.return_value.__enter__.return_value.get.call_args
    assert call.args[0] == "https://graph.facebook.com/v23.0/ig-123"
    assert call.kwargs["params"] == {"fields": "followers_count", "access_token": "tok"}


@patch("aeloria.analytics.followers.token_store")
@patch("aeloria.analytics.followers.httpx.Client")
def test_fetch_followers_400_raises_followers_error(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(400, text="bad")
    with pytest.raises(FollowersError):
        fetch_followers(_settings())


@patch("aeloria.analytics.followers.token_store")
@patch("aeloria.analytics.followers.httpx.Client")
def test_fetch_followers_retries_5xx_then_succeeds(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    client = mock_client_cls.return_value.__enter__.return_value
    client.get.side_effect = [
        _resp(503, text="oops"),
        _resp(200, json={"followers_count": 99}),
    ]
    assert fetch_followers(_settings()) == 99
    assert client.get.call_count == 2