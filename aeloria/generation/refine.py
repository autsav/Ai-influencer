"""Post-generation realism refinement: an upscale + skin/texture detail pass via a fal
detail-upscaler (clarity-upscaler), tuned low-creativity / high-resemblance so it adds
micro-texture without changing the face. The caller re-gates (upscalers can drift)."""
import base64
import os

import fal_client
import httpx

from aeloria.generation.face_gate import FaceGateError, passes_gate


class RefineError(Exception):
    pass


def refine_image(image_bytes: bytes, settings) -> bytes:
    os.environ["FAL_KEY"] = settings.fal_key
    data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()
    arguments = {
        "image_url": data_uri,
        "upscale_factor": settings.refine_upscale_factor,
        "creativity": settings.refine_creativity,
        "resemblance": settings.refine_resemblance,
        "prompt": "raw natural skin texture and fine detail",
    }
    try:
        result = fal_client.subscribe(settings.refine_model, arguments=arguments)
        images = result.get("images") or ([result["image"]] if result.get("image") else [])
        if not images:
            raise RefineError(f"fal refine returned no image: {result}")
        resp = httpx.get(images[0]["url"], timeout=90)
        resp.raise_for_status()
        return resp.content
    except RefineError:
        raise
    except Exception as e:
        raise RefineError(f"fal refine failed: {e}") from e


def refine_and_regate(image_bytes: bytes, settings, ref_embedding, base_sim):
    """Refine a gate-passing image, then re-check the face gate. Returns
    (final_bytes, sim). Falls back to the base image + base_sim on: refine disabled,
    a refine failure, or a refined image that fails the gate."""
    if not getattr(settings, "refine_enabled", False):
        return image_bytes, base_sim
    try:
        refined = refine_image(image_bytes, settings)
    except RefineError:
        return image_bytes, base_sim
    if ref_embedding is None:
        return refined, base_sim
    try:
        rsim, rok = passes_gate(refined, ref_embedding, settings.face_gate_threshold)
    except FaceGateError:
        return image_bytes, base_sim
    return (refined, rsim) if rok else (image_bytes, base_sim)
