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


def _build_prompt(
    char: CharacterConfig,
    scene: str,
    wardrobe: str = "",
    pose: str = "",
    camera_angle: str = "",
    tech_profile: str = "",
    aesthetic_tier: str = "",
) -> str:
    """Build a Flux-optimized prompt using natural-language description.

    The 10-layer Aeloria prompt structure:
    1. Opening shot type + aesthetic (natural language, not tags)
    2. Subject identity with physical details (LoRA trigger + visual DNA)
    3. Wardrobe with fabric, fit, neckline, texture, how it catches light
    4. Pose with explicit hand positioning (prevent extra hands)
    5. Environment with atmosphere, time, weather, mood
    6. Camera gear (lens, aperture, body, film stock)
    7. Aesthetic tier modifiers (moody / intimate / editorial)
    8. Skin realism (pores, freckles, peach fuzz, oil — anti-plastic)
    9. Identity lock (preserve LoRA face)
    10. Final quality + hand anatomy guard

    NOTE: Flux has no native negative prompt. Do NOT put "Avoid: ..." in the
    positive prompt — it pollutes generation. Use positive-only framing.

    Args:
        char: CharacterConfig with visual_dna, skin_realism, identity_lock,
              aesthetic_tiers (dict), wardrobe_archetypes (list)
        scene: Environment + atmosphere description
        wardrobe: Clothing detail. If empty and wardrobe_archetypes exist,
                  auto-selects a random archetype from character.json
        pose: Body positioning. If empty, auto-selects from creative database
        camera_angle: Lens + composition. If empty, auto-selects
        tech_profile: Film stock / lighting modifiers. Overrides aesthetic_tier default
        aesthetic_tier: Which look to apply — "editorial", "moody", "intimate_stories",
                        "fanvue_raw". If empty, defaults to "editorial"
    """
    v = char.visual_dna
    tiers = char.aesthetic_tiers or {}

    # ── 0. Resolve aesthetic tier ──────────────────────────────────────────
    tier_key = aesthetic_tier if aesthetic_tier in tiers else "editorial"
    tier_desc = tiers.get(tier_key, tiers.get("editorial", ""))

    # ── 1. Opening: shot type + aesthetic ───────────────────────────────────
    # Intimate stories tier uses different framing
    if tier_key == "intimate_stories":
        parts = ["An accidentally captured raw smartphone photograph"]
    elif tier_key == "fanvue_raw":
        parts = ["An unprocessed film scan, raw and unretouched"]
    else:
        parts = ["A candid fashion photograph"]

    # ── 2. Subject identity ──────────────────────────────────────────────────
    subject = (
        f"aeloria woman, {v.get('hair', 'auburn hair in a loose messy bun')}, "
        f"{v.get('eyes', 'warm green eyes')}, "
        f"{v.get('skin', 'fair skin with freckles across nose and cheeks, visible pores, peach fuzz')}"
    )
    parts.append(subject)

    # ── 3. Wardrobe ─────────────────────────────────────────────────────────
    if not wardrobe and char.wardrobe_archetypes:
        archetype = random.choice(char.wardrobe_archetypes)
        wardrobe = archetype.get("description", "")
        scene = archetype.get("scene", scene)  # blend archetype scene into prompt
    if wardrobe:
        # Ensure neckline is specified (prevents Flux wardrobe drift)
        if (
            "neck" not in wardrobe.lower()
            and "collar" not in wardrobe.lower()
            and "crop" not in wardrobe.lower()
            and "silhouette" not in wardrobe.lower()
        ):
            wardrobe = f"{wardrobe}, fitted silhouette following her body shape"
        parts.append(f"wearing {wardrobe}")

    # ── 4. Pose with explicit hand positioning ───────────────────────────────
    if pose:
        # Ensure hands are explicitly described to prevent extra hands
        hand_hint = ""
        if (
            "hand" not in pose.lower()
            and "arms" not in pose.lower()
            and "fingers" not in pose.lower()
        ):
            hand_hint = ", both hands visible and naturally positioned"
        parts.append(f"{pose}{hand_hint}")

    # ── 5. Environment + atmosphere ──────────────────────────────────────────
    parts.append(scene)

    # ── 6. Camera angle/composition ───────────────────────────────────────────
    if camera_angle:
        parts.append(camera_angle)

    # ── 7. Technical profile / aesthetic tier ────────────────────────────────
    if tech_profile:
        parts.append(tech_profile)
    elif tier_desc:
        parts.append(tier_desc)
    else:
        parts.append(
            "Shot on Kodak Portra 400, 50mm lens at f/2.0, natural depth of field"
        )

    # ── 8. Skin realism (anti-plastic) ──────────────────────────────────────
    if char.skin_realism:
        parts.append(char.skin_realism)
    else:
        parts.append(
            "Raw authentic skin with visible pores across the cheeks and nose, "
            "faint freckles, subtle natural redness around the nose, tiny skin bumps, "
            "fine peach fuzz catching the light, soft natural oil highlights on the nose "
            "and forehead — no smoothing, no beauty filter"
        )

    # ── 9. Identity lock ─────────────────────────────────────────────────────
    if char.identity_lock:
        parts.append(char.identity_lock)
    else:
        parts.append(
            "Preserve aeloria's exact identity — same face, auburn hair, "
            "same recognizable person. Do NOT change facial features or body shape"
        )

    # ── 10. Final quality + hand anatomy guard ────────────────────────────────
    if tier_key == "intimate_stories":
        parts.append(
            "Two hands only, correct anatomy, five fingers on each hand"
        )
    else:
        parts.append(
            "subtle film grain, raw unretouched editorial look, "
            "natural lighting. Two hands only, correct anatomy, five fingers on each hand"
        )

    # Join as natural-language paragraph (Flux prefers prose over tag lists)
    # Strip trailing periods to prevent double-periods on join
    cleaned = [p.rstrip(".") for p in parts]
    return ". ".join(cleaned)


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
    aesthetic_tier: str = "",
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

    prompt = _build_prompt(char, scene, wardrobe, pose, camera_angle, tech_profile, aesthetic_tier=aesthetic_tier)
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