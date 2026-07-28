"""Tests for lip-sync video generation."""
import pytest
from unittest.mock import MagicMock, patch, mock_open
from aeloria.generation.lipsync import lip_sync_video, LipSyncResult, LIPSYNC_COST_USD


@patch("httpx.get")
@patch("fal_client.subscribe")
def test_lip_sync_video_returns_video_bytes(mock_subscribe, mock_httpx_get):
    mock_subscribe.return_value = {"video": {"url": "https://example.com/lipsync.mp4"}}
    mock_httpx_get.return_value = MagicMock(content=b"fake-mp4-bytes", raise_for_status=lambda: None)

    settings = MagicMock()
    settings.fal_key = "fake-key"

    result = lip_sync_video(
        video_url="https://example.com/video.mp4",
        audio_url="https://example.com/audio.wav",
        settings=settings,
    )
    assert result.video_bytes == b"fake-mp4-bytes"
    assert result.cost_usd == LIPSYNC_COST_USD
    assert result.gen_params["model"] == "fal-ai/wav2lip"


@patch("fal_client.subscribe")
def test_lip_sync_no_audio_returns_empty(mock_subscribe):
    settings = MagicMock()
    settings.fal_key = "fake-key"

    result = lip_sync_video(
        video_url="https://example.com/video.mp4",
        audio_url=None,
        settings=settings,
    )
    assert result.video_bytes is None
    assert result.cost_usd == 0.0
    mock_subscribe.assert_not_called()


@patch("fal_client.subscribe")
def test_lip_sync_failure_returns_empty(mock_subscribe):
    mock_subscribe.side_effect = Exception("fal.ai error")

    settings = MagicMock()
    settings.fal_key = "fake-key"

    result = lip_sync_video(
        video_url="https://example.com/video.mp4",
        audio_url="https://example.com/audio.wav",
        settings=settings,
    )
    assert result.video_bytes is None
    assert result.cost_usd == 0.0


@patch("httpx.get")
@patch("fal_client.subscribe")
def test_lip_sync_alt_response_format(mock_subscribe, mock_httpx_get):
    """Handle alternate response format with output.video_url."""
    mock_subscribe.return_value = {"output": {"video_url": "https://example.com/ls.mp4"}}
    mock_httpx_get.return_value = MagicMock(content=b"mp4-data", raise_for_status=lambda: None)

    settings = MagicMock()
    settings.fal_key = "fake-key"

    result = lip_sync_video(
        video_url="https://example.com/v.mp4",
        audio_url="https://example.com/a.wav",
        settings=settings,
    )
    assert result.video_bytes == b"mp4-data"


@patch("httpx.get")
@patch("fal_client.subscribe")
def test_lip_sync_passes_correct_arguments(mock_subscribe, mock_httpx_get):
    mock_subscribe.return_value = {"video": {"url": "https://example.com/ls.mp4"}}
    mock_httpx_get.return_value = MagicMock(content=b"bytes", raise_for_status=lambda: None)

    settings = MagicMock()
    settings.fal_key = "fake-key"

    lip_sync_video(
        video_url="https://example.com/v.mp4",
        audio_url="https://example.com/a.wav",
        settings=settings,
        face_detect_boost=False,
        pad_size=20,
    )

    call_args = mock_subscribe.call_args
    args = call_args.kwargs["arguments"]
    assert args["video_url"] == "https://example.com/v.mp4"
    assert args["audio_url"] == "https://example.com/a.wav"
    assert args["face_detect_boost"] is False
    assert args["pad_size"] == 20


def test_lip_sync_result_defaults():
    r = LipSyncResult(video_bytes=None)
    assert r.video_bytes is None
    assert r.cost_usd == 0.0
    assert r.gen_params == {}