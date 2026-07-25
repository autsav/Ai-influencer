from unittest.mock import patch

import httpx
import pytest

from aeloria.analytics.insights import InsightsError, fetch_insights


def _settings():
    s = __import__("unittest.mock", fromlist=["MagicMock"]).MagicMock()
    s.graph_base = "https://graph.facebook.com/v23.0"
    s.kling_video_duration = 5
    return s


def _resp(status, json=None, text=None):
    req = httpx.Request("GET", "https://graph.facebook.com/x/insights")
    if json is not None:
        return httpx.Response(status, json=json, request=req)
    return httpx.Response(status, text=text or "", request=req)


@patch("aeloria.analytics.insights.token_store")
@patch("aeloria.analytics.insights.httpx.Client")
def test_fetch_insights_reel_normalizes_fields(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    payload = {
        "data": [
            {"name": "likes", "values": [{"value": 42}]},
            {"name": "comments", "values": [{"value": 3}]},
            {"name": "shares", "values": [{"value": 7}]},
            {"name": "saved", "values": [{"value": 5}]},
            {"name": "views", "values": [{"value": 1000}]},
            # Graph returns avg watch time in MILLISECONDS (live-verified)
            {"name": "ig_reels_avg_watch_time", "values": [{"value": 2500}]},
            {"name": "reach", "values": [{"value": 500}]},  # plain int on v23.0
        ]
    }
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(200, json=payload)
    out = fetch_insights(_settings(), "media-1", "reel")
    assert out == {
        "views": 1000, "likes": 42, "comments": 3, "shares": 7, "sends": 0,
        "saves": 5, "watch_through": pytest.approx(0.5), "non_follower_reach": None,
    }


@patch("aeloria.analytics.insights.token_store")
@patch("aeloria.analytics.insights.httpx.Client")
def test_fetch_insights_watch_through_capped_at_one(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    payload = {
        "data": [
            {"name": "ig_reels_avg_watch_time", "values": [{"value": 9000}]},  # 9s/5s = 1.8 -> cap 1.0
            {"name": "reach", "values": [{"value": 500}]},
        ]
    }
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(200, json=payload)
    out = fetch_insights(_settings(), "media-1", "reel")
    assert out["watch_through"] == 1.0


@patch("aeloria.analytics.insights.token_store")
@patch("aeloria.analytics.insights.httpx.Client")
def test_fetch_insights_image_defaults_missing_fields(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    # image insights: no shares/video_views/watch_time; reach is plain int (no breakdown)
    payload = {
        "data": [
            {"name": "likes", "values": [{"value": 10}]},
            {"name": "comments", "values": [{"value": 2}]},
            {"name": "saved", "values": [{"value": 1}]},
            {"name": "reach", "values": [{"value": 500}]},
        ]
    }
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(200, json=payload)
    out = fetch_insights(_settings(), "img-1", "static")
    assert out["views"] is None
    assert out["shares"] == 0
    assert out["watch_through"] is None
    assert out["non_follower_reach"] is None  # no follower breakdown for image
    assert out["likes"] == 10 and out["saves"] == 1


@patch("aeloria.analytics.insights.token_store")
@patch("aeloria.analytics.insights.httpx.Client")
def test_fetch_insights_400_raises_immediately(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(400, text="bad")
    with pytest.raises(InsightsError):
        fetch_insights(_settings(), "media-1", "reel")


@patch("aeloria.analytics.insights.token_store")
@patch("aeloria.analytics.insights.httpx.Client")
def test_fetch_insights_passes_token_and_metrics_in_request(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    mock_client_cls.return_value.__enter__.return_value.get.return_value = _resp(200, json={"data": []})
    fetch_insights(_settings(), "media-1", "reel")
    call = mock_client_cls.return_value.__enter__.return_value.get.call_args
    assert call.args[0].endswith("/media-1/insights")
    assert call.kwargs["params"]["access_token"] == "tok"
    # reel requests views (Graph v23.0 name) + avg watch time
    metrics = call.kwargs["params"]["metric"].split(",")
    assert "ig_reels_avg_watch_time" in metrics
    assert "views" in metrics
    assert "video_views" not in metrics  # stale pre-v23.0 name
    assert "saved" in metrics
    assert "saves" not in metrics        # stale pre-v23.0 name
    # No breakdown on v23.0 — every breakdown is rejected for these metrics
    assert "breakdown" not in call.kwargs["params"]


@patch("aeloria.analytics.insights.token_store")
@patch("aeloria.analytics.insights.httpx.Client")
def test_fetch_insights_reel_400_single_attempt_raises(mock_client_cls, mock_ts):
    mock_ts.get.return_value = "tok"
    get = mock_client_cls.return_value.__enter__.return_value.get
    get.side_effect = [_resp(400, text="bad")]
    with pytest.raises(InsightsError):
        fetch_insights(_settings(), "media-1", "reel")
    assert get.call_count == 1  # 400 is terminal — no breakdown-retry anymore