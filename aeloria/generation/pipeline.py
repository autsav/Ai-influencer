"""Aeloria generation pipeline — unified entry point. Soul 2.0 Pillar 8.

All generation flows through this module. It replaces direct calls to
worker.py from app.py and scheduler.py.

Workflow (generate):
  1. Validate brief
  2. Apply preset (if specified)
  3. Build prompt (prompt_builder)
  4. Generate image (fal_images)
  5. Verify face (face_gate)
  6. Refine (refine)
  7. Overlay text (post) — optional
  8. Return image path + metadata

All Soul 2.0 pillars wired here:
  - Pillar 1 (Engine):       fal_images via fal_images.generate_image
  - Pillar 2 (Soul ID):      LoRA + face_gate — wired in fal_images + worker
  - Pillar 3 (Presets):     presets.apply_preset — called in generate()
  - Pillar 4 (Realism):     realism_injector — positive clause + negative prompt
  - Pillar 5 (SOUL Inpaint): edit_image from edit.py

Re-exports run_pending so app.py and scheduler.py only need one import.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from aeloria.config import Settings
from aeloria.db.client import Db
from aeloria.generation.edit import edit_image
from aeloria.generation.worker import process_brief, run_pending

# Re-export run_pending for backward-compatible import from app.py / scheduler.py
__all__ = [
    "run_pending",      # from worker.py — existing batch entry point
    "generate",         # new single-generation entry point
    "GenerationResult", # return type for generate()
    "edit",             # from edit.py — SOUL inpaint
]


@dataclass
class GenerationResult:
    """Result of a pipeline.generate() call."""
    image_bytes: bytes
    cost_usd: float
    gen_params: dict
    face_similarity: float | None = None
    refined: bool = False
    caption: str | None = None


def generate(
    brief: dict,
    db: Db,
    settings: Settings,
    persona,          # Persona object from loader
    face_ref,         # face reference dict from load_reference
    r2=None,          # R2 client (optional, for storage)
    tg=None,          # Telegram client (optional, for notifications)
    preset: str | None = None,
) -> GenerationResult:
    """Generate a single image from a validated brief.

    Args:
        brief: dict with keys like location_override, wardrobe_override,
               mood_override, style_override, camera_override, pillar, etc.
        db: Db instance for budget tracking and record-keeping
        settings: Settings instance
        persona: loaded Persona from load_persona()
        face_ref: loaded face reference from load_reference()
        r2: optional R2 client for uploading generated images
        tg: optional Telegram client for notifications
        preset: optional preset name (e.g. "golden_hour_portrait") to apply
                before generation. User brief overrides preset on conflict.

    Returns:
        GenerationResult with image_bytes and metadata

    Raises:
        ValueError: if preset is given but not a valid preset name
    """
    # ── Step 1: Apply preset ──────────────────────────────────────────────────
    if preset:
        from aeloria.generation.presets import apply_preset, is_valid_preset
        if not is_valid_preset(preset):
            raise ValueError(f"unknown preset: {preset!r}")
        brief = apply_preset(brief, preset)

    # ── Step 2: Build prompt ─────────────────────────────────────────────────
    from aeloria.generation.prompt_builder import build_prompt
    # generate_post handles the full pipeline: build_prompt → fal_images →
    # face_gate → refine → DB write → Telegram notification.
    # It returns the post dict with image_bytes and metadata.
    post = process_brief(brief, db, settings, r2, persona, face_ref, tg=tg)

    return GenerationResult(
        image_bytes=post.get("image_bytes", b""),
        cost_usd=post.get("cost_usd", 0.0),
        gen_params=post.get("gen_params", {}),
        face_similarity=post.get("face_similarity"),
        refined=post.get("refined", False),
        caption=post.get("caption"),
    )


def edit(
    source_image: str,
    mask: str,
    instruction: str,
    settings: Settings | None = None,
) -> str:
    """SOUL Inpaint — inpaint a region of source_image with the given instruction.

    Uses FAL flux-kontext for precision editing (Soul 2.0 Pillar 5).

    Args:
        source_image: path or URL to the source image
        mask: path or URL to the mask (white = edit area, black = preserve)
        instruction: natural language edit instruction
        settings: optional Settings; uses get_settings() if None

    Returns:
        path to the edited image
    """
    return edit_image(source_image, mask, instruction, settings=settings)
