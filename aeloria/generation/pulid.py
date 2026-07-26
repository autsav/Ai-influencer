"""PuLID face identity integration for fal.ai FLUX.1.

Pass 1: Generates the base image with face identity conditioning via PuLID.
PuLID extracts a face embedding from a reference image and injects it into
the FLUX diffusion process, ensuring the generated face matches the reference.

fal.ai endpoint: fal-ai/pulid-flux (or equivalent)
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx

from aeloria.generation.consistency import (
    IdentityEmbedding,
    clamp_identity_weight,
    DEFAULT_PULID_WEIGHT,
)
from aeloria.generation.fal_images import ImageResult, GenerationError

log = logging.getLogger(__name__)

# fal.ai PuLID endpoint — Flux.1 + PuLID face identity
PULID_MODEL = "fal-ai/pulid-flux"
PULID_COST_USD = 0.06  # slightly more than base FLUX due to identity conditioning


def generate_with_pulid(
    prompt: str,
    reference_image_bytes: bytes,
    settings,
    aspect_ratio: str = "4:5",
    seed: int | None = None,
    pulid_weight: float = DEFAULT_PULID_WEIGHT,
    lora_url: str | None = None,
    lora_scale: float = 0.7,
    guidance_scale: float = 3.5,
    num_inference_steps: int = 40,
) -> ImageResult:
    """
    Pass 1: Generate image with PuLID face identity conditioning.

    Uses fal.ai's pulid-flux endpoint which injects a face embedding from
    the reference image into the FLUX diffusion process.

    Args:
        prompt: Full assembled prompt (quality anchor + identity + scene + camera)
        reference_image_bytes: Reference face image (PNG/JPEG bytes)
        settings: App settings (for fal API key)
        aspect_ratio: 4:5, 1:1, 16:9, 9:16
        seed: Reproducibility seed
        pulid_weight: Identity strength (clamped to [0.6, 1.1])
        lora_url: Custom LoRA URL (Aeloria face LoRA)
        lora_scale: LoRA strength
        guidance_scale: CFG guidance
        num_inference_steps: Diffusion steps

    Returns:
        ImageResult with generated image bytes + cost
    """
    import os
    import fal_client

    os.environ["FAL_KEY"] = settings.fal_key

    # Clamp identity weight to safe range
    pulid_weight = clamp_identity_weight(pulid_weight)

    # Encode reference image as data URI
    ref_data_uri = "data:image/png;base64," + base64.b64encode(reference_image_bytes).decode()

    arguments = {
        "prompt": prompt,
        "reference_image": ref_data_uri,
        "pulid_weight": pulid_weight,
        "aspect_ratio": aspect_ratio,
        "guidance_scale": guidance_scale,
        "num_inference_steps": num_inference_steps,
    }

    if seed is not None:
        arguments["seed"] = seed

    # Attach Aeloria LoRA if provided (dual identity: PuLID + LoRA)
    if lora_url:
        arguments["loras"] = [{
            "path": lora_url,
            "scale": lora_scale,
        }]

    log.info("PuLID generation: weight=%.2f, lora=%s, seed=%s", pulid_weight, bool(lora_url), seed)

    try:
        result = fal_client.subscribe(PULID_MODEL, arguments=arguments)
    except Exception as e:
        raise GenerationError(f"PuLID generation failed: {e}") from e

    images = result.get("images") or []
    if not images:
        raise GenerationError(f"PuLID returned no images: {result}")

    resp = httpx.get(images[0]["url"], timeout=60)
    resp.raise_for_status()

    log.info("PuLID generation complete: cost=$%.4f", PULID_COST_USD)
    return ImageResult(
        image_bytes=resp.content,
        cost_usd=PULID_COST_USD,
        gen_params={"model": PULID_MODEL, "pulid_weight": pulid_weight, **arguments},
    )