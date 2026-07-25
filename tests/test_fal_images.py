from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.fal_images import (
    FLUX_GENERAL_COST_USD,
    GenerationError,
    generate_image,
)


def _settings(
    lora="https://fal.media/lora.safetensors",
    ip_ref="https://r2/ref.png",
    model="rundiffusion-fal/juggernaut-flux-lora",
):
    s = MagicMock()
    s.fal_key = "k"
    s.aeloria_lora_url = lora
    s.aeloria_lora_scale = 0.78
    s.image_guidance_scale = 1.9
    s.image_model = model
    s.image_inference_steps = 30
    s.ip_adapter_ref_image_url = ip_ref
    s.ip_adapter_scale = 0.7
    s.ip_adapter_path = "InstantX/FLUX.1-dev-IP-Adapter"
    s.ip_adapter_image_encoder_path = "google/siglip-so400m-patch14-384"
    return s


@patch("aeloria.generation.fal_images.httpx.get")
@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_generate_image_happy_path_juggernaut(mock_sub, mock_get):
    mock_sub.return_value = {"images": [{"url": "https://fal.media/out.png"}]}
    mock_get.return_value = MagicMock(content=b"png-bytes", raise_for_status=MagicMock())

    r = generate_image("aeloria on porch, golden hour", settings=_settings())

    assert r.image_bytes == b"png-bytes"
    assert r.cost_usd == FLUX_GENERAL_COST_USD
    args, kwargs = mock_sub.call_args
    assert args[0] == "rundiffusion-fal/juggernaut-flux-lora"  # default base model
    loras = kwargs["arguments"]["loras"]
    assert loras[0]["path"] == "https://fal.media/lora.safetensors"
    assert loras[0]["scale"] == 0.78
    assert len(loras) == 1  # identity only by default
    assert kwargs["arguments"]["image_size"] == "portrait_16_9"
    assert kwargs["arguments"]["guidance_scale"] == 1.9
    assert kwargs["arguments"]["num_inference_steps"] == 30
    # Juggernaut has no ip_adapters param — identity rests on the LoRA (scale 0.78).
    assert "ip_adapters" not in kwargs["arguments"]


@patch("aeloria.generation.fal_images.httpx.get")
@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_flux_general_sends_ip_adapters(mock_sub, mock_get):
    mock_sub.return_value = {"images": [{"url": "https://fal.media/out.png"}]}
    mock_get.return_value = MagicMock(content=b"png-bytes", raise_for_status=MagicMock())

    generate_image("aeloria on porch", settings=_settings(model="fal-ai/flux-general"))

    args, kwargs = mock_sub.call_args
    assert args[0] == "fal-ai/flux-general"
    ipa = kwargs["arguments"]["ip_adapters"][0]
    assert ipa["image_url"] == "https://r2/ref.png"
    assert ipa["scale"] == 0.7
    assert ipa["path"] == "InstantX/FLUX.1-dev-IP-Adapter"
    assert ipa["image_encoder_path"] == "google/siglip-so400m-patch14-384"


@patch("aeloria.generation.fal_images.httpx.get")
@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_ip_adapter_omitted_when_ref_empty(mock_sub, mock_get):
    mock_sub.return_value = {"images": [{"url": "https://fal.media/out.png"}]}
    mock_get.return_value = MagicMock(content=b"png-bytes", raise_for_status=MagicMock())

    generate_image("aeloria on porch", settings=_settings(ip_ref="", model="fal-ai/flux-general"))

    args, kwargs = mock_sub.call_args
    assert args[0] == "fal-ai/flux-general"
    assert "ip_adapters" not in kwargs["arguments"]  # empty ref → omitted even on flux-general
    assert kwargs["arguments"]["loras"][0]["scale"] == 0.78


@patch("aeloria.generation.fal_images.httpx.get")
@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_extra_loras_appended_after_identity(mock_sub, mock_get):
    mock_sub.return_value = {"images": [{"url": "https://fal.media/out.png"}]}
    mock_get.return_value = MagicMock(content=b"png-bytes", raise_for_status=MagicMock())

    skin = [{"path": "https://hf/realism.safetensors", "scale": 0.6}]
    generate_image("aeloria on porch", settings=_settings(), extra_loras=skin)

    _, kwargs = mock_sub.call_args
    loras = kwargs["arguments"]["loras"]
    assert len(loras) == 2
    assert loras[0]["path"] == "https://fal.media/lora.safetensors"  # identity first
    assert loras[0]["scale"] == 0.78
    assert loras[1] == {"path": "https://hf/realism.safetensors", "scale": 0.6}


@patch("aeloria.generation.fal_images.httpx.get")
@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_guidance_scale_override(mock_sub, mock_get):
    mock_sub.return_value = {"images": [{"url": "https://fal.media/out.png"}]}
    mock_get.return_value = MagicMock(content=b"png-bytes", raise_for_status=MagicMock())

    generate_image("aeloria on porch", settings=_settings(), guidance_scale=3.5)
    _, kwargs = mock_sub.call_args
    assert kwargs["arguments"]["guidance_scale"] == 3.5


@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_no_images_raises(mock_sub):
    mock_sub.return_value = {"images": []}
    with pytest.raises(GenerationError):
        generate_image("x", settings=_settings())


def test_missing_lora_raises():
    with pytest.raises(GenerationError):
        generate_image("x", settings=_settings(lora=""))