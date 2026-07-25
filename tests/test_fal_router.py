from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.fal_router import (
    WORKFLOW_MODELS,
    WorkflowType,
    build_payload,
    cleanse_prompt,
)

IDENTITY = "https://cdn/aeloria-identity.safetensors"
REALISM = "https://huggingface.co/XLabs-AI/flux-RealismLora/resolve/main/lora.safetensors"


# ---- cleanse_prompt --------------------------------------------------------
def test_cleanse_strips_buzzwords_and_appends_camera_tokens():
    out = cleanse_prompt("aeloria on a porch, photorealistic, 8k, cinematic lighting, masterpiece")
    for bad in ("photorealistic", "8k", "cinematic", "masterpiece"):
        assert bad not in out.lower()
    assert "shot on 35mm lens" in out
    assert "raw JPEG texture" in out
    assert out.startswith("aeloria on a porch")


def test_cleanse_phrase_removed_without_comma_debris():
    out = cleanse_prompt("soft window light, cinematic lighting, warm tones")
    assert "cinematic" not in out.lower()
    assert ", ," not in out
    assert "soft window light" in out and "warm tones" in out


def test_cleanse_leaves_clean_prompt_unchanged():
    clean = "aeloria mid-laugh at a cafe, soft daylight"
    assert cleanse_prompt(clean) == clean


def test_cleanse_is_idempotent():
    once = cleanse_prompt("a face, hyperrealistic")
    assert cleanse_prompt(once) == once
    assert once.count("35mm") == 1


# ---- build_payload per workflow -------------------------------------------
def test_identity_locked_lora_payload():
    endpoint, body = build_payload(
        WorkflowType.IDENTITY_LOCKED_LORA, "aeloria on porch",
        identity_lora_url=IDENTITY, realism_lora_url=REALISM, seed=42)
    assert endpoint == "fal-ai/flux-lora"
    assert body["guidance_scale"] == 1.9
    assert body["num_inference_steps"] == 30
    assert body["seed"] == 42
    assert body["loras"] == [
        {"path": IDENTITY, "scale": 0.78},
        {"path": REALISM, "scale": 0.45},
    ]
    assert body["prompt"] == "aeloria on porch"


def test_overrides_win_over_defaults():
    _, body = build_payload(
        WorkflowType.IDENTITY_LOCKED_LORA, "x", identity_lora_url=IDENTITY,
        overrides={"identity_lora_scale": 0.85, "guidance_scale": 2.2})
    assert body["guidance_scale"] == 2.2
    assert body["loras"] == [{"path": IDENTITY, "scale": 0.85}]


def test_base_model_override_keeps_configured_endpoint():
    endpoint, _ = build_payload(
        WorkflowType.IDENTITY_LOCKED_LORA, "x", identity_lora_url=IDENTITY,
        base_model="rundiffusion-fal/juggernaut-flux-lora")
    assert endpoint == "rundiffusion-fal/juggernaut-flux-lora"


def test_out_of_box_photoreal_single_lora():
    endpoint, body = build_payload(
        WorkflowType.OUT_OF_BOX_PHOTOREAL, "aeloria", identity_lora_url=IDENTITY,
        realism_lora_url=REALISM)  # realism ignored for this workflow
    assert endpoint == "rundiffusion-fal/juggernaut-flux-lora"
    assert body["loras"] == [{"path": IDENTITY, "scale": 0.74}]


def test_in_painting_edit_requires_and_carries_image():
    endpoint, body = build_payload(
        WorkflowType.IN_PAINTING_EDIT, "swap the jacket",
        image_url="https://cdn/base.png", mask_url="https://cdn/mask.png")
    assert endpoint == "fal-ai/flux-kontext/dev"
    assert body["guidance_scale"] == 3.5 and body["num_inference_steps"] == 28
    assert body["image_url"] == "https://cdn/base.png"
    assert body["mask_url"] == "https://cdn/mask.png"


def test_in_painting_edit_missing_image_raises():
    with pytest.raises(ValueError, match="image_url"):
        build_payload(WorkflowType.IN_PAINTING_EDIT, "edit")


def test_multi_ref_blend_payload():
    endpoint, body = build_payload(
        WorkflowType.MULTI_REF_BLEND, "blend",
        reference_image_urls=["https://cdn/a.png", "https://cdn/b.png"])
    assert endpoint == "fal-ai/nano-banana-pro"
    assert body["aspect_ratio"] == "9:16"
    assert body["image_urls"] == ["https://cdn/a.png", "https://cdn/b.png"]


def test_high_res_editorial_payload():
    endpoint, body = build_payload(WorkflowType.HIGH_RES_EDITORIAL, "editorial")
    assert endpoint == "fal-ai/flux-pro/v1.1-ultra"
    assert body["raw"] is True and body["aspect_ratio"] == "9:16"
    assert "loras" not in body


def test_prompt_sanitized_for_every_workflow():
    for wf in WorkflowType:
        _, body = build_payload(
            wf, "aeloria, 8k, cinematic lighting",
            identity_lora_url=IDENTITY, image_url="https://cdn/base.png")
        assert "8k" not in body["prompt"].lower() and "cinematic" not in body["prompt"].lower()
        assert "shot on 35mm lens" in body["prompt"]


def test_every_workflow_mapped_to_endpoint():
    for wf in WorkflowType:
        assert WORKFLOW_MODELS[wf]["endpoint"]


# ---- generate_image integration (router path is live) ----------------------
def _settings():
    s = MagicMock()
    s.fal_key = "k"
    s.aeloria_lora_url = "https://cdn/identity.safetensors"
    s.realism_lora_url = REALISM
    s.image_model = "rundiffusion-fal/juggernaut-flux-lora"
    s.aeloria_lora_scale = 0.78
    s.realism_lora_scale = 0.45
    s.image_guidance_scale = 1.9
    s.image_inference_steps = 30
    return s


@patch("aeloria.generation.fal_images.httpx.get")
@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_generate_image_routes_high_res_editorial(mock_sub, mock_get):
    from aeloria.generation.fal_images import generate_image
    mock_sub.return_value = {"images": [{"url": "https://fal/out.png"}]}
    mock_get.return_value = MagicMock(content=b"png", raise_for_status=MagicMock())

    generate_image("a portrait, 8k", settings=_settings(),
                   workflow=WorkflowType.HIGH_RES_EDITORIAL)
    endpoint, kwargs = mock_sub.call_args.args[0], mock_sub.call_args.kwargs
    assert endpoint == "fal-ai/flux-pro/v1.1-ultra"
    assert kwargs["arguments"]["raw"] is True
    assert "8k" not in kwargs["arguments"]["prompt"].lower()  # sanitized


@patch("aeloria.generation.fal_images.httpx.get")
@patch("aeloria.generation.fal_images.fal_client.subscribe")
def test_generate_image_identity_workflow_keeps_configured_base_model(mock_sub, mock_get):
    from aeloria.generation.fal_images import generate_image
    mock_sub.return_value = {"images": [{"url": "https://fal/out.png"}]}
    mock_get.return_value = MagicMock(content=b"png", raise_for_status=MagicMock())

    generate_image("aeloria", settings=_settings(),
                   workflow=WorkflowType.IDENTITY_LOCKED_LORA)
    # LoRA workflow uses the configured (tested) base model, not the spec's flux-lora
    assert mock_sub.call_args.args[0] == "rundiffusion-fal/juggernaut-flux-lora"
    loras = mock_sub.call_args.kwargs["arguments"]["loras"]
    assert loras[0]["scale"] == 0.78 and loras[1]["scale"] == 0.45
