from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.refine import RefineError, refine_and_regate, refine_image


def _settings(enabled=True):
    s = MagicMock()
    s.fal_key = "k"
    s.refine_enabled = enabled
    s.refine_model = "fal-ai/clarity-upscaler"
    s.refine_upscale_factor = 2
    s.refine_creativity = 0.3
    s.refine_resemblance = 0.8
    s.face_gate_threshold = 0.35
    return s


@patch("aeloria.generation.refine.httpx.get")
@patch("aeloria.generation.refine.fal_client.subscribe")
def test_refine_image_calls_upscaler_and_returns_bytes(mock_sub, mock_get):
    mock_sub.return_value = {"images": [{"url": "https://fal/refined.png"}]}
    mock_get.return_value = MagicMock(content=b"refined", raise_for_status=MagicMock())
    out = refine_image(b"base", _settings())
    assert out == b"refined"
    args = mock_sub.call_args
    assert args.args[0] == "fal-ai/clarity-upscaler"
    a = args.kwargs["arguments"]
    assert a["image_url"].startswith("data:image/png;base64,")   # data-URI input
    assert a["creativity"] == 0.3 and a["resemblance"] == 0.8


@patch("aeloria.generation.refine.fal_client.subscribe", side_effect=RuntimeError("boom"))
def test_refine_image_raises_on_fal_error(_mock_sub):
    with pytest.raises(RefineError):
        refine_image(b"base", _settings())


@patch("aeloria.generation.refine.httpx.get", side_effect=Exception("cdn down"))
@patch("aeloria.generation.refine.fal_client.subscribe",
       return_value={"images": [{"url": "https://fal/r.png"}]})
def test_refine_image_download_failure_becomes_refine_error(_mock_sub, _mock_get):
    with pytest.raises(RefineError):
        refine_image(b"base", _settings())


def test_refine_and_regate_disabled_returns_base():
    out, sim = refine_and_regate(b"base", _settings(enabled=False), object(), 0.6)
    assert out == b"base" and sim == 0.6


@patch("aeloria.generation.refine.passes_gate", return_value=(0.71, True))
@patch("aeloria.generation.refine.refine_image", return_value=b"refined")
def test_refine_and_regate_returns_refined_when_gate_passes(_mi, _pg):
    out, sim = refine_and_regate(b"base", _settings(), object(), 0.6)
    assert out == b"refined" and sim == 0.71


@patch("aeloria.generation.refine.passes_gate", return_value=(0.20, False))
@patch("aeloria.generation.refine.refine_image", return_value=b"refined")
def test_refine_and_regate_falls_back_on_drift(_mi, _pg):
    out, sim = refine_and_regate(b"base", _settings(), object(), 0.6)
    assert out == b"base" and sim == 0.6   # refined drifted the face -> keep base


@patch("aeloria.generation.refine.refine_image", side_effect=RefineError("x"))
def test_refine_and_regate_falls_back_on_refine_error(_mi):
    out, sim = refine_and_regate(b"base", _settings(), object(), 0.6)
    assert out == b"base" and sim == 0.6
