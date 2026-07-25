"""Rule-based hashtag + on-screen keyword builder. $0, no LLM.

Niche tag pool is derived from persona niches. Relevance = any pool tag's
keyword appears in the brief's beat/caption_brief (case-insensitive word match).
Falls back to the core-niche tags when the brief has no overlapping words.
"""
import hashlib

from aeloria.persona.loader import Persona

# Punchy first-3s on-screen text hooks for Reels, keyed by activity category
# (#6 3-second text overlay). Deterministic pick by brief hash — POV / curiosity /
# loss-aversion / save framings. Falls back to activity words when no category.
_REEL_HOOKS: dict[str, list[str]] = {
    "get_ready": ["get ready with me", "the slow-morning face", "grwm, unhurried"],
    "style": ["outfit of the day", "one piece, styled 3 ways", "POV: you found the fit", "the piece everyone asks about"],
    "food": ["save this one", "the easiest thing i make", "what i actually eat"],
    "fitness": ["the 15-minute version", "no gym needed", "you're doing this wrong"],
    "work": ["behind the scenes", "how it really gets made", "a day on set"],
    "home": ["slow home reset", "the cozy corner nobody sees", "little home things"],
    "errands": ["come with me", "romanticize the mundane", "a slow errand day"],
    "social": ["come hang out", "a night out with me", "the good kind of chaos"],
    "travel": ["add this to the list", "you have to see this", "come with me here"],
    "wellness": ["your sign to slow down", "the reset you needed", "soft life hours"],
    "pet": ["ok but the dog", "my favorite coworker", "him, again"],
    "hobby": ["a little hobby hour", "making something slow", "the analog way"],
}

# Static, curated per-niche tag pools. Kept small so the "3-5 tags, no wall"
# persona rule is structurally enforced.
NICHE_TAGS: dict[str, list[str]] = {
    "wellness": ["#slowliving", "#forestlife", "#wellness", "#nature", "#mindful"],
    "fitness": ["#trailrunning", "#mobility", "#recovery", "#morningrun", "#fitness"],
    "travel": ["#travel", "#wander", "#cabinlife", "#getoutside", "#offgrid"],
    "gaming": ["#cozygaming", "#gaming", "#indiegames", "#cozyvibes"],
}

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "on", "in", "at", "to", "of",
    "with", "for", "is", "her", "she", "this", "that", "it",
}

MAX_TAGS = 5
MIN_TAGS = 3


def _niche_keys(persona: Persona) -> list[str]:
    # core first, then secondary, then arcs/experiments — order matters for fallback.
    keys = []
    raw = [persona.niches.core, persona.niches.secondary, *persona.niches.arcs, *persona.niches.experiments]
    for label in raw:
        for k in NICHE_TAGS:
            if k in label.lower() and k not in keys:
                keys.append(k)
    if not keys:
        keys = ["wellness"]
    return keys


def _beat_words(brief: dict) -> set[str]:
    # Activity beats are snake_case ids (e.g. "travel_sightseeing"); split on "_"
    # so the real words feed hashtag relevance, not one dead compound token.
    text = f"{brief.get('beat', '')} {brief.get('caption_brief', '')}".lower().replace("_", " ")
    return {w for w in text.split() if w and w not in STOPWORDS}


def _pick_hashtags(persona: Persona, brief: dict) -> list[str]:
    words = _beat_words(brief)
    keys = _niche_keys(persona)
    pool: list[str] = []
    for k in keys:
        for tag in NICHE_TAGS.get(k, []):
            if tag not in pool:
                pool.append(tag)
    # Relevance: a tag is relevant if any of its non-# keywords appear in the beat.
    relevant = [t for t in pool if any(w in t[1:] for w in words)]
    chosen = relevant[:MAX_TAGS]
    if len(chosen) < MIN_TAGS:
        for t in pool:
            if t not in chosen:
                chosen.append(t)
            if len(chosen) >= MIN_TAGS:
                break
    return chosen[:MAX_TAGS]


def _on_screen_keywords(brief: dict) -> list[str]:
    if brief.get("slot_type") != "reel":
        return []
    # Prefer a punchy category hook for the first-3s overlay (the reel overlay
    # only burns keywords[0]); deterministic pick per brief.
    hooks = _REEL_HOOKS.get(brief.get("activity_category"))
    if hooks:
        key = str(brief.get("id") or brief.get("beat", ""))
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return [hooks[h % len(hooks)]]
    # Fallback: beat may be a snake_case activity id ("travel_sightseeing") —
    # normalize "_" to spaces so the overlay reads "travel sightseeing".
    beat = brief.get("beat", "").replace("_", " ")
    words = [w for w in beat.split() if w and w.lower() not in STOPWORDS]
    return words[:3]


def build(persona: Persona, brief: dict) -> dict:
    return {
        "hashtags": _pick_hashtags(persona, brief),
        "on_screen_keywords": _on_screen_keywords(brief),
    }