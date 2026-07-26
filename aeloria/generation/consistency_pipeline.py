"""Two-pass character consistency pipeline orchestrator.

Coordinates:
1. Identity extraction from reference face
2. Pass 1: Generation with PuLID + LoRA (or LoRA-only fallback)
3. Face detection on Pass 1 output
4. Pass 2: Face detailer refinement (conditional)
5. Identity verification (face gate)

Usage:
    from aeloria.generation.consistency_pipeline import generate_consistent
    result = generate_consistent(brief, persona, settings, reference_bytes)
"""
from __future__ import annotations

import logging
from typing import Optional

from aeloria.generation.consistency import (
    ConsistencyResult,
    FaceCrop,
    detect_face_crop,
    extract_identity,
    clamp_identity_weight,
    DEFAULT_PULID_WEIGHT,
    DEFAULT_FACE_DENOISE,
)
from aeloria.generation.face_gate import passes_gate, FaceGateError
from aeloria.generation.fal_images import generate_image, ImageResult, GenerationError
from aeloria.generation.face_detailer import maybe_refine_face
from aeloria.generation.prompt_builder import build_prompt
from aeloria.persona.loader import Persona

log = logging.getLogger(__name__)


def generate_consistent(
    brief: dict,
    persona: Persona,
    settings,
    reference_bytes: Optional[bytes] = None,
    use_pulid: bool = True,
    pulid_weight: float = DEFAULT_PULID_WEIGHT,
    face_denoise: float = DEFAULT_FACE_DENOISE,
    seed: int | None = None,
) -> ConsistencyResult:
    """
    Run the full two-pass character consistency pipeline.

    Args:
        brief: Generation brief (prompt_seed, pillar, wardrobe, etc.)
        persona: Loaded Aeloria persona
        settings: App settings
        reference_bytes: Reference face image bytes (for PuLID + face gate)
        use_pulid: If True, use PuLID for Pass 1. If False, fall back to LoRA-only.
        pulid_weight: PuLID identity weight (clamped to [0.6, 1.1])
        face_denoise: Face detailer denoise (clamped to [0.15, 0.40])
        seed: Reproducibility seed

    Returns:
        ConsistencyResult with final image, identity scores, and metadata.
    """
    # ── Step 1: Build prompt ─────────────────────────────────────────────────
    prompt = build_prompt(persona, brief)
    log.info("Consistency pipeline: prompt built (%d chars)", len(prompt))

    # ── Step 2: Pass 1 — Base generation ─────────────────────────────────────
    pass1_bytes: Optional[bytes] = None
    pass1_cost: float = 0.0
    used_pulid = False

    if use_pulid and reference_bytes:
        try:
            from aeloria.generation.pulid import generate_with_pulid
            lora_url = getattr(settings, "aeloria_lora_url", None)
            lora_scale = getattr(settings, "aeloria_lora_scale", 0.7)
            result = generate_with_pulid(
                prompt=prompt,
                reference_image_bytes=reference_bytes,
                settings=settings,
                aspect_ratio=brief.get("aspect_ratio", "4:5"),
                seed=seed,
                pulid_weight=pulid_weight,
                lora_url=lora_url,
                lora_scale=lora_scale,
            )
            pass1_bytes = result.image_bytes
            pass1_cost = result.cost_usd
            used_pulid = True
            log.info("Pass 1: PuLID generation complete ($%.4f)", pass1_cost)
        except GenerationError as e:
            log.warning("PuLID generation failed, falling back to LoRA-only: %s", e)

    if pass1_bytes is None:
        # LoRA-only fallback (existing pipeline)
        result = generate_image(
            prompt=prompt,
            settings=settings,
            aspect_ratio=brief.get("aspect_ratio", "4:5"),
            seed=seed,
        )
        pass1_bytes = result.image_bytes
        pass1_cost = result.cost_usd
        log.info("Pass 1: LoRA-only generation complete ($%.4f)", pass1_cost)

    # ── Step 3: Evaluate Pass 1 identity ─────────────────────────────────────
    pass1_score = 0.0
    face_crop: Optional[FaceCrop] = None

    # Detect face for Pass 2 decision
    face_crop = detect_face_crop(pass1_bytes)

    # Face gate check (if we have a reference embedding)
    if reference_bytes:
        try:
            from aeloria.generation.face_gate import embed_face, similarity, load_reference
            # Try loading the stored reference embedding
            ref_path = getattr(settings, "face_ref_path", None)
            if ref_path:
                import os
                if os.path.exists(ref_path):
                    ref_emb = load_reference(ref_path)
                    img_emb = embed_face(pass1_bytes)
                    pass1_score = similarity(img_emb, ref_emb)
                    log.info("Pass 1 identity score: %.4f (threshold: %.2f)",
                             pass1_score, settings.face_gate_threshold)
        except FaceGateError as e:
            log.warning("Face gate check failed: %s", e)
        except Exception as e:
            log.warning("Identity scoring error: %s", e)

    # ── Step 4: Pass 2 — Face detailer refinement (conditional) ──────────────
    final_bytes = pass1_bytes
    detail_applied = False
    pass2_cost = 0.0

    try:
        refined, detail_applied = maybe_refine_face(
            image_bytes=pass1_bytes,
            settings=settings,
            face_crop=face_crop,
            denoise=face_denoise,
            seed=seed,
        )
        if detail_applied:
            from aeloria.generation.face_detailer import FACE_DETAIL_COST_USD
            final_bytes = refined
            pass2_cost = FACE_DETAIL_COST_USD
            log.info("Pass 2: Face detailer applied ($%.4f)", pass2_cost)
    except Exception as e:
        log.warning("Pass 2 failed, using Pass 1 output: %s", e)

    # ── Step 5: Final identity verification ──────────────────────────────────
    final_score = pass1_score
    passes = False

    if reference_bytes:
        try:
            from aeloria.generation.face_gate import embed_face, similarity, load_reference
            ref_path = getattr(settings, "face_ref_path", None)
            if ref_path:
                import os
                if os.path.exists(ref_path):
                    ref_emb = load_reference(ref_path)
                    img_emb = embed_face(final_bytes)
                    final_score = similarity(img_emb, ref_emb)
                    passes = final_score >= settings.face_gate_threshold
                    if detail_applied:
                        log.info("Pass 2 identity score: %.4f (delta: %+.4f)",
                                 final_score, final_score - pass1_score)
        except FaceGateError as e:
            log.warning("Final face gate check failed: %s", e)
        except Exception as e:
            log.warning("Final identity scoring error: %s", e)

    total_cost = pass1_cost + pass2_cost

    log.info(
        "Consistency pipeline complete: pulid=%s, detail_pass=%s, "
        "pass1_score=%.4f, final_score=%.4f, passes_gate=%s, cost=$%.4f",
        used_pulid, detail_applied, pass1_score, final_score, passes, total_cost,
    )

    return ConsistencyResult(
        image_bytes=final_bytes,
        identity_score=final_score,
        passes_gate=passes,
        pass1_score=pass1_score,
        pass2_score=final_score,
        detail_pass_applied=detail_applied,
        cost_usd=total_cost,
        face_crop=face_crop,
    )