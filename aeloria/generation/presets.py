"""Soul 2.0 preset catalogue — Soul 2.0 Pillar 3.

Maps high-level intent descriptors to concrete prompt overrides.
Compose with explicit user brief — user brief always wins on conflict.

Usage:
    brief = apply_preset(user_brief, "golden_hour_portrait")
    brief = apply_preset(user_brief, "candid_street")
    brief = apply_preset(user_brief, "slow_living")

All overrides are lowercase dict keys matching brief field names.
"""

from __future__ import annotations

from typing import Literal

# ── Preset definitions ─────────────────────────────────────────────────────────

PRESETS: dict[str, dict] = {
    # ── Cinematic / Editorial ────────────────────────────────────────────────
    "golden_hour_portrait": {
        "mood_override": "warm golden hour glow",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Tri-X 400 film",
    },
    "blue_hour": {
        "mood_override": "cool blue hour, fading dusk light",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Kodak Portra 800",
    },
    "editorial_warm": {
        "mood_override": "warm cinematic light, rich amber tones",
        "style_override": "film_editorial",
        "camera_override": "shot on Hasselblad 500C, Fujifilm Pro 400H",
    },
    "editorial_cool": {
        "mood_override": "cool cinematic light, blue-grey tones",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Cinestill 800T",
    },
    "fashion": {
        "mood_override": "high fashion, studio lighting",
        "style_override": "film_editorial",
        "camera_override": "shot on Canon AE-1, Kodak Portra 400",
    },

    # ── Candid / Street ─────────────────────────────────────────────────────
    "candid_street": {
        "style_override": "candid",
        "mood_override": "spontaneous and alive",
    },
    "flash_candid": {
        "style_override": "flash_candid",
        "mood_override": "raw disposable camera energy",
        "camera_override": "shot on disposable flash camera, heavy grain",
    },
    "street_urban": {
        "style_override": "candid",
        "mood_override": "urban grit, real life in motion",
        "camera_override": "shot on Nikon FM2, Kodak Gold 200",
    },

    # ── Paparazzi / Night ────────────────────────────────────────────────────
    "paparazzi_night": {
        "style_override": "paparazzi_night",
        "mood_override": "moody and dramatic",
        "camera_override": "shot on Canon 1V, Cinestill 800T, pushed 2 stops",
    },
    "urban_evening": {
        "style_override": "paparazzi_night",
        "mood_override": "city night life, moody",
    },

    # ── Lifestyle / Slow Living ──────────────────────────────────────────────
    "slow_living": {
        "pillar": "slow_living",
        "mood_override": "unhurried and present",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Kodak Portra 400",
    },
    "morning_routine": {
        "mood_override": "morning light, unhurried",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Kodak Portra 800, available light",
    },
    "golden": {
        "mood_override": "warm afternoon light, golden hour",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Kodak Portra 400",
    },
    "quiet_moment": {
        "mood_override": "quiet and still, present in the moment",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Kodak Portra 800, available light",
    },

    # ── Seasonal / Atmosphere ────────────────────────────────────────────────
    "autumn": {
        "mood_override": "autumn afternoon light, warm amber tones",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Kodak Portra 400",
    },
    "spring": {
        "mood_override": "soft spring light, fresh",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Fujifilm Pro 400H",
    },
    "overcast": {
        "mood_override": "soft diffused overcast light, even skin exposure",
        "style_override": "film_editorial",
        "camera_override": "shot on Leica M6, Kodak Portra 800",
    },
    "rain": {
        "mood_override": "rainy day, moody and atmospheric",
        "style_override": "paparazzi_night",
        "camera_override": "shot on Canon 1V, Cinestill 800T",
    },

    # ── Close-up / Detail ─────────────────────────────────────────────────────
    "portrait_close": {
        "style_override": "film_editorial",
        "mood_override": "intimate close-up",
        "camera_override": "shot on Leica M6, 85mm, Kodak Portra 800",
    },
    "beauty": {
        "mood_override": "beauty close-up, clean light",
        "style_override": "film_editorial",
        "camera_override": "shot on Hasselblad 500C, Kodak Portra 400",
    },

    # ── Fashion / Editorial ───────────────────────────────────────────────────
    "evening_glam": {
        "mood_override": "evening glamour, warm tungsten light",
        "style_override": "film_editorial",
        "camera_override": "shot on Canon AE-1, Kodak Portra 800",
    },
    "studio": {
        "mood_override": "studio light, clean and polished",
        "style_override": "film_editorial",
        "camera_override": "shot on Hasselblad 500C, Kodak Portra 400",
    },
}

PresetName = Literal[tuple(PRESETS.keys())]


def apply_preset(brief: dict, preset_name: str) -> dict:
    """Merge preset overrides into a user brief.

    Preset provides defaults; brief provides overrides.
    brief wins on any conflicting keys.

    Args:
        brief: user-provided brief dict (may be empty {})
        preset_name: key from PRESETS (e.g. "golden_hour_portrait")

    Returns:
        merged dict with brief fields taking priority over preset fields

    Raises:
        KeyError: if preset_name is not in PRESETS
    """
    preset = PRESETS[preset_name]
    # brief overrides preset — order matters
    return {**preset, **brief}


def get_preset_names() -> list[str]:
    """Return sorted list of all available preset names."""
    return sorted(PRESETS.keys())


def get_preset_names_by_tag(tag: str) -> list[str]:
    """Return preset names that include the given tag in their docstring.

    Note: this searches preset names directly for the tag substring.
    """
    return [name for name in PRESETS if tag.lower() in name.lower()]


def is_valid_preset(name: str) -> bool:
    """Return True if name is a known preset key."""
    return name in PRESETS
