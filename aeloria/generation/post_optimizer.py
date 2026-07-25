"""Post optimizer — nudge briefs toward save-worthy, share-worthy content.

Saves correlate with:
- Content that feels "saved for later" (travel inspiration, style reference, mood board)
- Carousels outperform single images for saves
- Quote overlays and actionable captions increase saves
- Specificity beats generality ("saved for when I need this rooftop" vs "nice photo")

Shares correlate with:
- Strong first hook (punchy line, question, POV framing)
- Emotionally resonant (awe, dry humor, anti-hustle)
- POV framing ("when you..." / "POV: ...")

Reach drivers:
- Reels get initial push from algorithm; saves extend reach window
- High save rate = algorithm keeps promoting
"""

from typing import Optional


# Save-bait modifiers — these should be prepended or baked into brief generation
SAVE_BAIT_ELEMENTS = [
    "note the exact rooftop location for future reference",
    "save this for the next late night",
    "saving this for when I need this exact mood",
    "save this for the next city trip",
    "the kind of shot you screenshot immediately",
]

# Share-bait hooks — specific framings that drive screenshot/shares
SHARE_BAIT_HOOKS = [
    "POV: you found the rooftop everyone talks about",
    "when the city gives you blue hour for free",
    "the 2am walk home that fixes everything",
    "saving this alley for the next rain",
    "the night the city was completely yours",
]

# Reach-optimized film styles (algorithm favors these)
REACH_STYLES = [
    "flash_candid",
    "paparazzi_night",
    "street_editorial",
    "blue_hour",
]


def optimize_for_saves(brief: dict) -> dict:
    """Mutate a brief dict to increase save probability.

    Adds design notes and nudges style/content toward "saved for later" territory.
    Returns a new dict (does not mutate input).
    """
    optimized = dict(brief)

    # Add save-bait design note if not present
    if "design_notes" not in optimized:
        optimized["design_notes"] = ""

    notes = []

    # Always add save-bait note — specificity drives saves
    notes.append(
        "save-bait: include enough location detail that viewer wants to screenshot "
        "for their next trip — specificity beats generality"
    )

    # Carousel nudge (saves are higher on carousels)
    if optimized.get("content_type") in (None, "static", ""):
        optimized["content_type"] = "carousel"
        notes.append("carousel format: 3-5 slides, each a different angle/mood of the same scene — more saves than static")

    # Share hook prepended to caption_brief
    share_hook = SHARE_BAIT_HOOKS[hash(str(brief)) % len(SHARE_BAIT_HOOKS)]
    current_caption = optimized.get("caption_brief", "")
    if current_caption:
        optimized["caption_brief"] = f"{share_hook}\n{current_caption}"
    else:
        optimized["caption_brief"] = share_hook
        notes.append(f"share-hook prepended: {share_hook}")

    # Design notes for visual save-bait
    notes.append("design: avoid cluttered frames — clean compositions with one focal point get more saves")
    optimized["design_notes"] = " | ".join(notes)

    return optimized


def reach_optimized_style(style: str) -> str:
    """Return the reach-optimized variant of a film style.

    Reels algorithm pushes flash_candid / paparazzi_night harder than
    golden_hour / film_editorial in 2026 — hard truth.
    """
    if style in REACH_STYLES:
        return style
    return "flash_candid"  # fallback — always-on reach boost


def optimize_for_shares(brief: dict) -> dict:
    """Nudge brief toward share-ability: POV framing, emotional hooks."""
    optimized = dict(brief)

    # POV pre-header
    pov = SHARE_BAIT_HOOKS[hash(str(brief) + "share") % len(SHARE_BAIT_HOOKS)]
    current_caption = optimized.get("caption_brief", "")
    if current_caption and not current_caption.startswith("POV:"):
        optimized["caption_brief"] = f"POV: {current_caption}"

    # Remove anything that kills shareability
    # (overly specific product mentions, direct CTAs — "link in bio" type kills shares)
    caption = optimized.get("caption_brief", "")
    bad_patterns = ["link in bio", "DM me", "comment below", "follow for"]
    for pat in bad_patterns:
        if pat.lower() in caption.lower():
            caption = caption.lower().replace(pat.lower(), "")
    optimized["caption_brief"] = caption.strip()

    return optimized


def should_post_as_reel(brief: dict) -> bool:
    """Decide if this brief should be a Reel vs Carousel vs Static.

    Reels get algorithmic reach boost but need motion/narrative.
    Carousels get saves boost.
    """
    beat = brief.get("beat", "")

    # Movement-oriented beats → Reel
    reel_beats = ["mid-stride", "walking", "run", "moving", "transit", "platform"]
    if any(rb in beat.lower() for rb in reel_beats):
        return True

    # Static beauty beats → Carousel (higher save rate)
    carousel_beats = ["rooftop", "reading", "doing nothing", "late coffee", "quiet detail"]
    if any(cb in beat.lower() for cb in carousel_beats):
        return False

    # Default: Reel (reach extension)
    return True
