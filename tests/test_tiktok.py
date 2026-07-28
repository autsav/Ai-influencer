"""Tests for TikTok Content Posting API publisher."""
import pytest
from unittest.mock import MagicMock, patch
from aeloria.publishing.tiktok import publish_video, check_tiktok_auth, TikTokError


@patch("httpx.Client.post")
def test_publish_video_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "video": {"video_id": "7234567890"},
            "share_url": "https://www.tiktok.com/@user/video/7234567890",
        },
        "error": {},
    }
    mock_post.return_value = mock_response

    settings = MagicMock()
    settings.tiktok_access_token = "test-token"
    settings.tiktok_open_id = "test-open-id"

    video_id, share_url = publish_video(
        settings,
        "https://example.com/video.mp4",
        "Test caption #AI",
    )
    assert video_id == "7234567890"
    assert "tiktok.com" in share_url


@patch("httpx.Client.post")
def test_publish_video_truncates_long_caption(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"video": {"video_id": "123"}, "share_url": "https://tiktok.com/@u/v/123"},
        "error": {},
    }
    mock_post.return_value = mock_response

    settings = MagicMock()
    settings.tiktok_access_token = "test-token"

    long_caption = "A" * 300
    publish_video(settings, "https://example.com/v.mp4", long_caption)

    # Verify the title was truncated to 150
    call_args = mock_post.call_args
    sent_title = call_args.kwargs["json"]["post_info"]["title"]
    assert len(sent_title) == 150


def test_publish_video_no_token_raises():
    settings = MagicMock()
    settings.tiktok_access_token = ""
    with pytest.raises(TikTokError, match="not configured"):
        publish_video(settings, "https://example.com/v.mp4", "cap")


@patch("httpx.Client.post")
def test_publish_video_api_error_raises(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {},
        "error": {"code": "access_token_invalid", "message": "Access token expired"},
    }
    mock_post.return_value = mock_response

    settings = MagicMock()
    settings.tiktok_access_token = "expired-token"
    with pytest.raises(TikTokError, match="Access token expired"):
        publish_video(settings, "https://example.com/v.mp4", "cap")


@patch("httpx.Client.post")
def test_publish_video_http_error_raises(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"
    mock_post.return_value = mock_response

    settings = MagicMock()
    settings.tiktok_access_token = "bad-token"
    with pytest.raises(TikTokError, match="init failed"):
        publish_video(settings, "https://example.com/v.mp4", "cap")


def test_check_tiktok_auth_configured():
    settings = MagicMock()
    settings.tiktok_access_token = "token123"
    assert check_tiktok_auth(settings) is True


def test_check_tiktok_auth_not_configured():
    settings = MagicMock()
    settings.tiktok_access_token = ""
    assert check_tiktok_auth(settings) is False