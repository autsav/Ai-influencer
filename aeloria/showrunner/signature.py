"""Signature scheduler: an ownable signature beat fires every
SIGNATURE_EVERY_DAYS, rotating through fixed AI-entrepreneur anchors. The caller
tracks how many signatures have already been emitted (rotation index)."""

SIGNATURE_EVERY_DAYS = 7

# Recurring ownable beats — recognizable Aeloria signatures (the AI entrepreneur
# anchors from the persona wedge). Rotated, never LLM-generated.
SIGNATURE_BEATS = [
    "minimal home office at golden hour, MacBook glow on her face",
    "clean desk morning stillness, coffee steam, laptop closed",
    "walking to a coworking space in morning light, backpack on",
    "café corner table with a workflow on screen, flat white beside it",
]


def signature_beat(rotation_index: int) -> str:
    """Return the signature beat for a given rotation count (wraps)."""
    return SIGNATURE_BEATS[rotation_index % len(SIGNATURE_BEATS)]


def signature_for_day(
    day_index: int,
    last_signature_day_index: int | None,
    signatures_emitted: int = 0,
) -> str | None:
    """Return a signature beat if at least SIGNATURE_EVERY_DAYS have passed
    since the last signature, else None. `last_signature_day_index=None` means
    no prior signature — the first one lands at day 7 (treat base as 0).
    `signatures_emitted` selects the rotation beat to emit."""
    base = 0 if last_signature_day_index is None else last_signature_day_index
    if day_index - base < SIGNATURE_EVERY_DAYS:
        return None
    return signature_beat(signatures_emitted)