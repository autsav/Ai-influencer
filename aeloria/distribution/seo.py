"""Rule-based hashtag + on-screen keyword builder. $0, no LLM.

Niche tag pool is derived from persona niches. Relevance = any pool tag's
keyword appears in the brief's beat/caption_brief (case-insensitive word match).
Falls back to the core-niche tags when the brief has no overlapping words.

U5 (2026-08-17): Reel on-screen hook picks weighted by `learnings.json`
per-pillar hook-type scores when ≥3 entries exist; otherwise static
`_REEL_HOOKS` is used. Wires ChampionChallenger-style learned rotation.
"""
import hashlib
import json
import random
from pathlib import Path
from typing import Optional

from aeloria.persona.loader import Persona

DEFAULT_LEARNINGS_PATH = Path("aeloria/distribution/learnings.json")
LEARNED_HOOK_THRESHOLD = 3  # ≥3 hook-type posts per pillar before weighted pick

# Punchy first-3s on-screen text hooks for Reels, keyed by activity category
# (#6 3-second text overlay). Deterministic pick by brief hash — POV / curiosity /
# loss-aversion / save framings. Falls back to activity words when no category.
_REEL_HOOKS: dict[str, list[str]] = {
    "founder_lifestyle": ["this saves me 6 hours every day", "the workflow nobody's talking about", "POV: you found the tool", "built this in one coffee"],
    "style": ["outfit of the day", "founder fit check", "smart casual, always"],
    "food": ["save this one", "coffee shop build", "where I actually work"],
    "fitness": ["the 15-minute version", "no gym needed", "energy for the build"],
    "work": ["this AI replaced 3 employees", "behind the workflow", "watch this automate"],
    "social": ["come hang out", "coworking with me", "the good kind of networking"],
    "personal_growth": ["your sign to start building", "AI creates freedom", "the book that changed my approach"],
}

# Static, curated per-niche tag pools. Kept small so the "3-5 tags, no wall"
# persona rule is structurally enforced.
NICHE_TAGS: dict[str, list[str]] = {
    "ai automation": ["#AIAutomation", "#AIWorkflow", "#AutomationFirst", "#BusinessAI", "#FutureOfWork"],
    "ai tools": ["#AITools", "#AIForBusiness", "#TechTools", "#Productivity", "#AI"],
    "founder lifestyle": ["#FounderLife", "#EntrepreneurLife", "#StartupFounder", "#FounderMode", "#TechLifestyle"],
    "case studies": ["#BusinessRedesign", "#AITransformation", "#SmallBusinessAI", "#CaseStudy", "#BusinessGrowth"],
    "future of business": ["#FutureOfWork", "#AI future", "#BusinessTransformation", "#AutomationFirst", "#NextGenBusiness"],
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
        keys = ["ai automation"]
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


def _on_screen_keywords(brief: dict, learnings_path: Optional[Path] = None) -> list[str]:
    if brief.get("slot_type") != "reel":
        return []
    activity_category = brief.get("activity_category")
    hooks = _REEL_HOOKS.get(activity_category)
    if hooks:
        # U5: weighted pick from `_REEL_HOOKS[activity_category]` when
        # learnings.json has ≥`LEARNED_HOOK_THRESHOLD` hook-type entries for
        # this pillar. Else fall back to deterministic-by-brief-hash pick.
        learned_idx = _learned_hook_index(activity_category, hooks, learnings_path)
        if learned_idx is not None:
            return [hooks[learned_idx % len(hooks)]]
        key = str(brief.get("id") or brief.get("beat", ""))
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return [hooks[h % len(hooks)]]
    # Fallback: beat may be a snake_case activity id ("travel_sightseeing") —
    # normalize "_" to spaces so the overlay reads "travel sightseeing".
    beat = brief.get("beat", "").replace("_", " ")
    words = [w for w in beat.split() if w and w.lower() not in STOPWORDS]
    return words[:3]


def _learned_hook_index(
    activity_category: Optional[str],
    hooks: list[str],
    learnings_path: Optional[Path] = None,
) -> Optional[int]:
    """Return weighted-random hook index for `activity_category`, or None.

    Reads `learnings.json["posts"]`, filters to `content_pillar ==
    activity_category`, aggregates per-hook-type scores (k_factor), and
    weighted-picks an index mapped by `hook_type % len(hooks)`.

    Returns None when `activity_category` is falsy, no posts exist for the
    pillar, or there are fewer than `LEARNED_HOOK_THRESHOLD` entries —
    in which case the caller falls back to the deterministic static pick.
    """
    if not activity_category or not hooks:
        return None
    path = learnings_path or DEFAULT_LEARNINGS_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    posts = data.get("posts", []) or []
    pillar_posts = [p for p in posts if p.get("content_pillar") == activity_category]
    if len(pillar_posts) < LEARNED_HOOK_THRESHOLD:
        return None
    # Aggregate score per hook_type
    scores: dict[str, float] = {}
    for p in pillar_posts:
        ht = p.get("hook_type") or "unknown"
        scores[ht] = scores.get(ht, 0.0) + float(p.get("k_factor", 0.0))
    if not scores or max(scores.values(), default=0.0) <= 0.0:
        return None
    hook_types = list(scores.keys())
    weights = [scores[h] for h in hook_types]
    chosen_type = random.choices(hook_types, weights=weights, k=1)[0]
    # Deterministic index: stable hash of hook_type → hook position so the
    # same winning hook_type always lands on the same hook string.
    h = int(hashlib.md5(chosen_type.encode()).hexdigest(), 16)
    return h % len(hooks)


def build(persona: Persona, brief: dict) -> dict:
    return {
        "hashtags": _pick_hashtags(persona, brief),
        "on_screen_keywords": _on_screen_keywords(brief),
    }