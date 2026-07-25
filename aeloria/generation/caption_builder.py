"""Caption builder — viral hooks in Luna's voice.

Produces punchy, 3-line-max captions with:
- First line: punchy hook (not a question, not a platitude)
- Body: dry urban observation that earns the hook
- Tone: cool, dry, anti-hustle, city-observant — never generic influencer
- NO: hashtag walls, generic gratitude, "link in bio" energy
"""

import random
from typing import Optional


# Luna-specific caption patterns — dry wit, city observation, anti-hustle
_HOOK_TEMPLATES = [
    "the {noun} {verb} better from {location}",
    "{observation} — {punchline}",
    "a good {noun} needs a good {descriptor}",
    "slow is still {compliment}",
    "the city {verb} and i {action}",
    "{observation}. that's the whole point.",
    "the {noun} {verb} isn't the {noun} you're {verb}ing",
    "i came for the {noun} and stayed for the {noun}",
    "{first_line}. {second_line}.",
    "the {urban_detail} is always the whole point",
]

_OBSERVATIONS = [
    "the city owes me nothing and gives me everything",
    "2am is the best hour and nobody will convince me otherwise",
    "rooftops fix most things",
    "the shortcut is always the main road",
    "walking like you have somewhere to be is a performance",
    "a good night needs a good rooftop",
    "slow is still fast enough",
    "the food at 2am is always better than the food at 8pm",
    "neon on wet pavement is the only aesthetic that matters",
    "the city doesn't care if you're productive and neither do i",
    "some feelings only move when your feet do",
    "the rooftop after everyone's left is the real rooftop",
]

_PUNCHLINES = [
    "and that's the gift",
    "that's the whole point",
    "the city knows",
    "indifference is underrated",
    "nothing is the plan",
    "i'm right here",
]

_URBAN_DETAILS = [
    "neon reflection on wet pavement",
    "rooftop after rain",
    "corner shop glow at dusk",
    "2am street light halo",
    "blue hour on the bridge",
    "alley shortcut",
]


def _build_hook(style: str = "default") -> str:
    """Build the first-line hook from Luna's pattern set."""
    if style == "observation":
        return random.choice(_OBSERVATIONS)
    elif style == "punchline":
        return random.choice(_PUNCHLINES)
    else:
        return random.choice(_OBSERVATIONS)


def _build_body(hook: str, caption_brief: str, beat: str) -> str:
    """Build caption body from beat + persona brief."""
    # If caption_brief is strong, use it as the body
    if caption_brief and len(caption_brief) > 10:
        return caption_brief
    # Fallback: generate from beat context
    bodies = {
        "late coffee": "the morning rush is optional",
        "reading, phone away": "we confused being reachable with being alive",
        "doing nothing": "doing nothing is a skill we were taught to be ashamed of",
        "rooftop neon dusk": "the skyline is better from the rooftop",
        "late-night bodega": "the bodega is the real community centre",
        "blue hour bridge": "blue hour is a mood and the city is always in it",
        "neon alley shortcut": "the shortcut through the alley is always the whole point of the walk",
        "subway platform": "the train is never late to the party you're having with yourself",
        "street mid-stride": "walking like you have somewhere to be is a performance",
        "post-studio glow": "the studio after everyone's left is the real space",
        "arrival wander": "travel slowly enough and a new city stops being a checklist",
        "cafe corner": "the point of the trip was never the landmarks",
        "quiet detail": "the city everyone photographs isn't the one you'll remember",
    }
    return bodies.get(beat, caption_brief or "slow is still fast enough")


def build_caption(
    caption_brief: Optional[str] = None,
    beat: str = "doing nothing",
    persona_name: str = "luna",
    style: str = "default",
) -> str:
    """Build a viral caption for Luna.

    Args:
        caption_brief: the beat's caption_brief — used as body if provided
        beat: the beat key — used to look up fallback body copy
        persona_name: unused placeholder, for signature consistency
        style: 'default' or 'observation' (longer hook, shorter body)

    Returns:
        A 2-3 line caption: hook on line 1, body on line 2, optional sign-off on line 3
    """
    hook = _build_hook(style=style)
    body = _build_body(hook, caption_brief or "", beat)

    # 3-line structure: hook / body / sign-off
    lines = [hook, body]

    # Occasional sign-off (not always — keeps it fresh)
    if random.random() > 0.5:
        signoffs = [
            f"({persona_name})",
            "— still here",
            "city, night",
        ]
        lines.append(random.choice(signoffs))

    return "\n".join(lines)


def caption_for_beat(beat_dict: dict, style: str = "default") -> str:
    """Build caption directly from a beat dict (beat_for / beat_for_chapter output)."""
    return build_caption(
        caption_brief=beat_dict.get("caption_brief"),
        beat=beat_dict.get("beat", "doing nothing"),
        persona_name="luna",
        style=style,
    )
