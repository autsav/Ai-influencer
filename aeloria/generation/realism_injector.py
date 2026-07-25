"""Anti-plastic realism injector — Soul 2.0 Pillar 4.

Single source of truth for negative prompting and raw skin texturing.
Both prompt_builder.py and fal_images.py call into this module.

Architecture:
  - NEGATIVE_PROMPT: appended to every generation's negative prompt slot
  - inject_realism(): composes the raw-skin texture clause appended to the
    positive prompt (extracted from prompt_builder._SKIN)
  - build_negative_prompt(): returns the canonical negative prompt string
  - build_skin_texture_clause(): returns the skin realism clause for positives

The core principle: every generation must describe skin texture explicitly in
the positive prompt AND deny plastic/retouched skin in the negative.
"""

# ── Negative prompt — appended to every generation ────────────────────────────

NEGATIVE_PROMPT = (
    "airbrushed skin, plastic skin, waxy skin, beauty filter, CGI look, "
    "distorted anatomy, exaggerated proportions, duplicate limbs, low resolution, "
    "smooth skin, retouched skin, soft focus skin, glaze, "
    "blank dull expression, stiff centered pose, "
    "Do not change her facial features or body shape."
)

# ── Positive skin clause — extracted from prompt_builder._SKIN ───────────────────

SKIN_TEXTURE_CLAUSE = (
    "Her skin stays raw and real — visible pores across the cheeks and nose, "
    "peach fuzz on the upper lip and forehead, vellus hair on the T-zone and cheeks, "
    "fine texture on the forehead and around the nostrils, a natural skin tone "
    "with subtle variation, faint under-eye darkness, slight redness at the nose "
    "wings, and real pore-level detail everywhere, flyaway hairs catching the light. "
    "No smoothing, no beauty filter, no plastic. Real skin texture preserved."
)

# ── Film/digital texture overlays (appended to positive prompt by style) ─────────

FILM_TEXTURE = (
    "subtle film grain, natural preserved skin texture with pores and fine detail, "
    "a raw unretouched look, faint sensor noise"
)

CITY_TEXTURE = (
    "clean modern digital capture, sharp city detail in the background, "
    "natural preserved skin texture with pores and fine detail, "
    "a raw unretouched editorial look"
)


def build_negative_prompt() -> str:
    """Return the canonical negative prompt. Call this for every generation."""
    return NEGATIVE_PROMPT


def build_skin_texture_clause() -> str:
    """Return the raw-skin texture clause for the positive prompt."""
    return SKIN_TEXTURE_CLAUSE


def inject_realism(prompt: str) -> str:
    """Append the raw-skin realism clause to a prompt.

    Use this when the caller is building a prompt without going through
    prompt_builder (e.g. direct fal_images.generate_image calls).
    """
    return f"{prompt.strip()} {SKIN_TEXTURE_CLAUSE}"


def build_positive_texture(style: str) -> str:
    """Return the appropriate texture overlay for the given style label.

    Args:
        style: one of "film_editorial", "flash_candid", "paparazzi_night",
               "city", or "default"
    Returns:
        texture clause string to append to the positive prompt
    """
    return {
        "film_editorial": FILM_TEXTURE,
        "flash_candid": (
            "heavy film grain, harsh direct flash, skin lit with hot specular "
            "light, visible texture and imperfections, raw overexposed look"
        ),
        "paparazzi_night": (
            "low-light skin only warmth against near-black background, "
            "available light, natural preserved skin texture with pores and fine detail"
        ),
        "city": CITY_TEXTURE,
    }.get(style, FILM_TEXTURE)
