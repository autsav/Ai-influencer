"""Adaptive face gate threshold — adjusts based on scene type.

Wide shots and motion-blur scenes routinely score lower on face similarity
but may still be perfectly good images. Instead of a flat 0.35 threshold,
the gate adapts: closeups require higher scores, wide shots get more leniency.

Usage:
    from aeloria.generation.adaptive_gate import adaptive_threshold
    threshold = adaptive_threshold(brief, base=0.35)
"""
import logging

log = logging.getLogger(__name__)

# Scene type → threshold adjustment
# Closeups: face is large, identity should be very clear → stricter
# Wide shots: face is small, lower similarity is acceptable → more lenient
# Motion blur: diffusion may soften face features → more lenient
_SCENE_ADJUSTMENTS = {
    "closeup": +0.05,       # 0.40 — face fills frame, expect high match
    "portrait": 0.0,        # 0.35 — standard
    "medium": -0.03,        # 0.32 — half body, face smaller
    "wide": -0.07,          # 0.28 — full body or environmental, face is small
    "motion_blur": -0.05,   # 0.30 — motion blur softens features
    "crowd": -0.05,         # 0.30 — face among others, harder to match
}

# Clamps — never go below or above these
MIN_THRESHOLD = 0.20
MAX_THRESHOLD = 0.50


def detect_scene_type(brief: dict) -> str:
    """Infer scene type from brief fields.

    Looks at prompt_seed keywords and style_override to classify the shot.
    """
    seed = (brief.get("prompt_seed") or "").lower()
    style = (brief.get("style_override") or "").lower()

    # Motion blur indicators
    if any(kw in seed for kw in ["motion blur", "motion-blurred", "panning", "long exposure"]):
        return "motion_blur"

    # Crowd indicators
    if any(kw in seed for kw in ["crowd", "surrounded by people", "busy street"]):
        return "crowd"

    # Closeup indicators
    if any(kw in seed for kw in ["closeup", "close-up", "extreme close", "face fill"]):
        return "closeup"

    # Wide shot indicators
    if any(kw in seed for kw in ["wide shot", "full body", "environmental", "wide-angle", "far away"]):
        return "wide"

    # Medium shot indicators
    if any(kw in seed for kw in ["medium shot", "half body", "three-quarter", "waist up"]):
        return "medium"

    # Style-based heuristics
    if style == "paparazzi_night":
        return "wide"  # paparazzi shots are typically distant/telephoto

    return "portrait"  # default


def adaptive_threshold(brief: dict, base: float = 0.35) -> float:
    """Calculate an adaptive face gate threshold based on scene type.

    Args:
        brief: Generation brief with prompt_seed, style_override, etc.
        base: Base threshold (default 0.35 from config)

    Returns:
        Adjusted threshold clamped to [MIN_THRESHOLD, MAX_THRESHOLD]
    """
    scene = detect_scene_type(brief)
    adjustment = _SCENE_ADJUSTMENTS.get(scene, 0.0)
    threshold = base + adjustment
    threshold = max(MIN_THRESHOLD, min(MAX_THRESHOLD, threshold))

    log.info(
        "Adaptive gate: scene=%s, base=%.2f, adjustment=%+.2f, threshold=%.2f",
        scene, base, adjustment, threshold,
    )
    return threshold