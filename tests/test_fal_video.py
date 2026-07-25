from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.fal_video import VideoResult, generate_video


def _settings(model="fal-ai/kling-image-to-video", cost=0.20, duration=5):
    s = MagicMock()
    s.fal_key = "k"
    s.kling_model = model
    s.kling_video_cost_usd = cost
    s.kling_video_duration = duration
    return s


@patch("aeloria.generation.fal_video.httpx.get")
@patch("aeloria.generation.fal_video.fal_client.subscribe")
def test_generate_video_happy_path(mock_sub, mock_get):
    mock_sub.return_value = {"video": {"url": "https://fal.media/out.mp4"}}
    mock_get.return_value = MagicMock(content=b"mp4-bytes", raise_for_status=MagicMock())

    r = generate_video("https://r2/hero.png", "aeloria tea pour, gentle motion",
                       settings=_settings())

    assert r.video_bytes == b"mp4-bytes"
    assert r.cost_usd == 0.20
    args, kwargs = mock_sub.call_args
    assert args[0] == "fal-ai/kling-image-to-video"
    a = kwargs["arguments"]
    assert a["image_url"] == "https://r2/hero.png"
    assert a["prompt"] == "aeloria tea pour, gentle motion"
    assert a["duration"] == "5"
    assert r.gen_params["model"] == "fal-ai/kling-image-to-video"


@patch("aeloria.generation.fal_video.fal_client.subscribe")
def test_generate_video_no_url_raises(mock_sub):
    mock_sub.return_value = {"video": None}
    with pytest.raises(Exception):
        generate_video("https://r2/hero.png", "x", settings=_settings())