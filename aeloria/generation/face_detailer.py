"""Face Detailer — Pass 2: localized inpainting to fix facial artifacts.

After Pass 1 generates the full image, the face detailer:
1. Detects the face region (via InsightFace)
2. Crops a face region with padding
3. Runs a low-denoise inpainting pass to fix artifacts (eyes, mouth, skin)
4. Composites the refined face back into the original image

Denoise is clamped to [0.15, 0.40] — high enough to fix artifacts,
low enough to prevent identity mutation.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional

import httpx

from aeloria.generation.consistency import (
    FaceCrop,
    clamp_denoise,
    DEFAULT_FACE_DENOISE,
)
from aeloria.generation.fal_images import GenerationError

log = logging.getLogger(__name__)

# fal.ai inpainting endpoint for face refinement
FACE_DETAIL_MODEL = "fal-ai/flux-dev/inpainting"
FACE_DETAIL_COST_USD = 0.04

# Face detail prompt — focused on fixing artifacts, not changing identity
FACE_DETAIL_PROMPT = (
    "detailed face, correct facial features, sharp eyes, natural skin texture, "
    "visible pores, peach fuzz, symmetrical features, natural lighting on face, "
    "no morphological artifacts, no extra fingers, correct eye color"
)


def refine_face(
    image_bytes: bytes,
    face_crop: FaceCrop,
    settings,
    denoise: float = DEFAULT_FACE_DENOISE,
    seed: int | None = None,
) -> bytes:
    """
    Pass 2: Run a face detailer inpainting pass on the detected face region.

    Uses fal.ai's flux-dev inpainting endpoint with a mask over the face area.
    Low denoise (0.25-0.35) fixes artifacts without changing identity.

    Args:
        image_bytes: Full generated image from Pass 1
        face_crop: Detected face region (from detect_face_crop)
        settings: App settings
        denoise: Denoise strength (clamped to [0.15, 0.40])
        seed: Reproducibility seed

    Returns:
        Refined image bytes (full image with face region updated)
    """
    import os
    import fal_client
    import numpy as np
    import cv2

    os.environ["FAL_KEY"] = settings.fal_key
    denoise = clamp_denoise(denoise)

    # Decode the base image
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)

    # Create a mask (white = area to inpaint, black = keep)
    mask = np.zeros(img.shape[:2], dtype=np.uint8)
    x1, y1, x2, y2 = face_crop.bbox
    # Fill the face region in the mask
    mask[y1:y2, x1:x2] = 255

    # Encode image and mask as base64
    _, img_encoded = cv2.imencode(".png", img)
    img_data_uri = "data:image/png;base64," + base64.b64encode(img_encoded).decode()

    _, mask_encoded = cv2.imencode(".png", mask)
    mask_data_uri = "data:image/png;base64," + base64.b64encode(mask_encoded).decode()

    arguments = {
        "image": img_data_uri,
        "mask": mask_data_uri,
        "prompt": FACE_DETAIL_PROMPT,
        "num_inference_steps": 20,  # fewer steps for inpainting
        "guidance_scale": 7.5,
        "denoising_strength": denoise,
        "strength": denoise,  # some endpoints use 'strength'
    }

    if seed is not None:
        arguments["seed"] = seed

    log.info(
        "Face detailer: crop=%s, face_size=%d, denoise=%.2f",
        face_crop.bbox, face_crop.face_size, denoise,
    )

    try:
        result = fal_client.subscribe(FACE_DETAIL_MODEL, arguments=arguments)
    except Exception as e:
        raise GenerationError(f"Face detailer failed: {e}") from e

    images = result.get("images") or []
    if not images:
        raise GenerationError(f"Face detailer returned no images: {result}")

    resp = httpx.get(images[0]["url"], timeout=60)
    resp.raise_for_status()

    log.info("Face detailer complete: denoise=%.2f, cost=$%.4f", denoise, FACE_DETAIL_COST_USD)
    return resp.content


def maybe_refine_face(
    image_bytes: bytes,
    settings,
    face_crop: Optional[FaceCrop] = None,
    denoise: float = DEFAULT_FACE_DENOISE,
    seed: int | None = None,
) -> tuple[bytes, bool]:
    """
    Conditionally run the face detailer pass.
    Only runs if:
    - face_crop is detected and face is small enough to benefit (< 256px)
    - settings.face_detailer_enabled is True

    Returns:
        (refined_bytes or original_bytes, detail_pass_applied)
    """
    if not getattr(settings, "face_detailer_enabled", False):
        return image_bytes, False

    if face_crop is None:
        face_crop = detect_face_crop(image_bytes)
        if face_crop is None:
            return image_bytes, False

    if not face_crop.needs_detail_pass:
        log.info("Face is %dpx — large enough, skipping detail pass", face_crop.face_size)
        return image_bytes, False

    try:
        refined = refine_face(image_bytes, face_crop, settings, denoise=denoise, seed=seed)
        return refined, True
    except GenerationError as e:
        log.warning("Face detailer failed, using base image: %s", e)
        return image_bytes, False


# Late import to avoid circular dependency
from aeloria.generation.consistency import detect_face_crop  # noqa: E402