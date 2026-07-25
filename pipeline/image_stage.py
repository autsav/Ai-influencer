"""Async image generation stage — FAL Flux LoRA or ComfyUI backend.

Wraps the existing aeloria.generation.fal_images for pipeline use,
adds async execution and JSON-config-driven parameters.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

from pipeline.config_loader import CharacterConfig

logger = logging.getLogger(__name__)

_ASPECT_TO_SIZE = {
    "9:16": "portrait_16_9",
    "4:5": "portrait_16_9",  # 896×1152 = 0.778, closer to 4:5 (0.8) than portrait_4_3 (0.75)
    "1:1": "square_hd",
    "16:9": "landscape_16_9",
}


@dataclass
class ImageResult:
    image_bytes: bytes
    seed: int
    cost_usd: float
    gen_time: float
    params: dict


def _build_prompt(char: CharacterConfig, scene: str, wardrobe: str = "",
                  pose: str = "", camera_angle: str = "",
                  tech_profile: str = "") -> str:
    """Build a Flux-ready prompt from character config + scene parameters."""
    v = char.visual_dna
    parts = [
        f"A candid fashion photograph",
        f"aeloria woman, {v.get('hair', 'auburn hair')}, {v.get('eyes', 'green eyes')}, "
        f"{v.get('skin', 'fair skin with freckles')}",
        scene,
    ]
    if wardrobe:
        parts.append(f"wearing {wardrobe}")
    if pose:
        parts.append(f"Pose: {pose}")
    if camera_angle:
        parts.append(camera_angle)
    if tech_profile:
        parts.append(tech_profile)
    if char.skin_realism:
        parts.append(char.skin_realism)
    if char.identity_lock:
        parts.append(char.identity_lock)
    parts.append(
        "Shot on Kodak Portra 400, natural depth of field, subtle film grain, "
        "raw unretouched editorial look."
    )
    if char.negative_prompt:
        parts.append(f"Avoid: {char.negative_prompt}")
    return ". ".join(parts)


def _post_process(img: Image.Image) -> Image.Image:
    """WB + sharpen + vignette — zero API cost."""
    img = ImageEnhance.Color(img).enhance(0.95)
    img = ImageEnhance.Brightness(img).enhance(1.03)
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
    w, h = img.size
    arr = np.array(img, dtype=np.float32) / 255.0
    cy, cx = h / 2, w / 2
    max_r = (cx**2 + cy**2) ** 0.5
    yy, xx = np.ogrid[:h, :w]
    dist = ((xx - cx)**2 + (yy - cy)**2) ** 0.5 / max_r
    vignette = np.clip(1 - 0.15 * dist, 0.7, 1.0)
    arr *= vignette[..., np.newaxis]
    return Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8))


async def generate_image(
    char: CharacterConfig,
    scene: str,
    wardrobe: str = "",
    pose: str = "",
    camera_angle: str = "",
    tech_profile: str = "",
    seed: int | None = None,
    dry_run: bool = False,
) -> ImageResult:
    """Generate a single image asynchronously via FAL.

    Args:
        char: Character config (LoRA URL, scale, model, etc.)
        scene: Scene description
        wardrobe: Optional wardrobe override
        pose: Optional pose description
        camera_angle: Optional camera angle/composition
        tech_profile: Optional technical/photographic profile modifier
        seed: Reproducibility seed
        dry_run: If True, return a placeholder without calling FAL
    """
    if seed is None:
        seed = random.randint(0, 2**31)

    prompt = _build_prompt(char, scene, wardrobe, pose, camera_angle, tech_profile)
    image_size = _ASPECT_TO_SIZE.get(char.aspect_ratio, "portrait_4_3")

    logger.info("Image stage: seed=%d scene=%s", seed, scene[:60])

    if dry_run:
        logger.info("Dry run — skipping FAL call")
        return ImageResult(
            image_bytes=b"",
            seed=seed,
            cost_usd=0.0,
            gen_time=0.0,
            params={"prompt": prompt, "dry_run": True},
        )

    # Run FAL in executor (fal_client.subscribe is blocking)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _fal_generate, prompt, char, image_size, seed
    )
    return result


def _fal_generate(prompt: str, char: CharacterConfig, image_size: str, seed: int) -> ImageResult:
    """Blocking FAL call — runs in executor."""
    import fal_client

    os.environ.setdefault("FAL_KEY", os.environ.get("FAL_KEY", ""))

    arguments = {
        "prompt": prompt,
        "loras": [{"path": char.lora_url, "scale": char.lora_scale}],
        "guidance_scale": char.guidance_scale,
        "num_inference_steps": char.num_inference_steps,
        "image_size": image_size,
        "num_images": 1,
        "enable_safety_checker": False,
        "seed": seed,
    }

    t0 = time.time()
    result = fal_client.subscribe(char.image_model, arguments=arguments)
    elapsed = time.time() - t0

    img_url = result["images"][0]["url"]
    resp = httpx.get(img_url, timeout=120)
    resp.raise_for_status()

    # Post-process
    img = Image.open(io.BytesIO(resp.content))
    img = _post_process(img)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)

    logger.info("Image generated in %.1fs", elapsed)
    return ImageResult(
        image_bytes=buf.read(),
        seed=seed,
        cost_usd=0.05,
        gen_time=elapsed,
        params={"prompt": prompt, "model": char.image_model, "seed": seed},
    )