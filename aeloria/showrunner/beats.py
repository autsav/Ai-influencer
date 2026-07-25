"""Deterministic beat library. Each entry is {beat, prompt_seed, caption_brief};
the beat sheet rotates by week_index so week-over-week varies without an LLM.
`caption_brief` follows the persona voice (anti-hustle, first-line hook).

Niches are short keys (the showrunner stores these as the arc `niche`):
  core      = wellness + nature (slow living, forest life)
  secondary = fitness (trail runs, bodyweight, recovery)
  arcs      = travel (monthly trips away, always returning)
"""

_E = lambda beat, prompt_seed, caption_brief: {  # noqa: E731
    "beat": beat, "prompt_seed": prompt_seed, "caption_brief": caption_brief,
}

BEATS = {
    "core": {
        "tease": [
            _E("porch tea golden hour",
               "aeloria on the porch steps with a clay mug of tea, golden hour light through the trees",
               "your 5am routine is a coping mechanism — slow mornings aren't laziness"),
            _E("creek trail",
               "aeloria barefoot on the mossy trail down to the creek, soft forest light",
               "the forest doesn't owe you productivity and neither do you"),
        ],
        "peak": [
            _E("restoring the roof",
               "aeloria on a ladder patching the cabin roof, tools scattered, dappled light",
               "the leaking roof again. progress is slow and that's the whole point"),
            _E("stubborn garden",
               "aeloria kneeling in the vegetable garden, dirt on her hands, late afternoon",
               "every seed I plant is a small argument against the hustle"),
            _E("woodpecker steals screws",
               "aeloria laughing near the woodpile, a woodpecker on the fence post",
               "the woodpecker stole my screws again — we have an understanding now"),
        ],
        "callback": [
            _E("porch tea callback",
               "aeloria back on the porch steps at golden hour, same mug, quieter light",
               "back where we started — slow wins, every time"),
        ],
    },
    "secondary": {
        "tease": [
            _E("trail run dawn",
               "aeloria stretching on the forest road at first light, trail shoes laced",
               "trail runs beat the gym because nothing is chasing you but you"),
        ],
        "peak": [
            _E("bodyweight on the porch",
               "aeloria mid push-up on the porch steps, mist in the trees behind her",
               "bodyweight, fresh air, no mirror — fitness that doesn't need a performance"),
            _E("recovery stretch creek",
               "aeloria stretching by the creek post-run, hands in the cold water",
               "recovery isn't weakness — it's how you stay able to come back tomorrow"),
        ],
        "callback": [
            _E("trail run callback",
               "aeloria back on the forest road at first light, slower pace",
               "same trail, slower — the goal was never the distance"),
        ],
    },
    "arcs": {
        "tease": [
            _E("packing for the trip",
               "aeloria packing a canvas bag on the porch, map on the table",
               "leaving the forest house for a few days — even slow living packs a bag"),
        ],
        "peak": [
            _E("train window",
               "aeloria leaning against a train window, landscape blurring past, soft light",
               "motion after stillness — the trip is the disruption and the relief"),
            _E("unfamiliar coast",
               "aeloria on an unfamiliar rocky coast, wind in her hair, late sun",
               "the sea doesn't care about your routine and that's the gift"),
        ],
        "callback": [
            _E("returning home",
               "aeloria walking back up the mossy trail to the cabin, bag over her shoulder",
               "every trip ends on this trail — the forest house waits"),
        ],
    },
}

_VALID_PHASES = ("tease", "peak", "callback")


def beat_for(niche: str, phase: str, week_index: int) -> dict:
    """Return the beat entry for niche×phase, rotating by week_index. Raises
    ValueError on unknown niche or terminal/unknown phase (caller never asks
    for `done` — there are no beats for a completed arc)."""
    if niche not in BEATS:
        raise ValueError(f"unknown niche: {niche!r}")
    if phase not in _VALID_PHASES:
        raise ValueError(f"unknown or terminal phase: {phase!r}")
    entries = BEATS[niche][phase]
    return dict(entries[week_index % len(entries)])


# ---- Pillar library (Phase: 360-day calendar) ----------------------------
# Subjects are LOCATION-NEUTRAL: beat_for_chapter places them in a location +
# season. Never bake "porch"/"forest"/a city into a subject here.
PILLAR_BEATS = {
    "slow_living": [
        {"beat": "morning tea", "subject": "aeloria cradling a clay mug of morning tea, unhurried, soft expression",
         "caption_brief": "your 5am routine is a coping mechanism — slow mornings aren't laziness"},
        {"beat": "reading, phone away", "subject": "aeloria curled with a worn paperback, no phone in sight",
         "caption_brief": "we confused being reachable with being alive"},
        {"beat": "doing nothing", "subject": "aeloria sitting still, hands around a warm cup, watching the light",
         "caption_brief": "doing nothing is a skill we were taught to be ashamed of"},
    ],
    "self_healing": [
        {"beat": "journaling", "subject": "aeloria journaling slowly at a wooden table, warm lamp light",
         "caption_brief": "healing isn't a glow-up. some days it's just writing the sentence down"},
        {"beat": "resting", "subject": "aeloria resting with eyes closed, a blanket around her shoulders, calm",
         "caption_brief": "rest is not the reward for finishing. it's how you keep going"},
        {"beat": "slow walk", "subject": "aeloria on a slow reflective walk, hands in her sleeves, gentle expression",
         "caption_brief": "some feelings only move when your feet do"},
    ],
    "yoga": [
        {"beat": "sun salutation", "subject": "aeloria flowing through a slow sun salutation on a woven mat, calm focus",
         "caption_brief": "i don't stretch to fix myself. i stretch to say hello to myself"},
        {"beat": "seated breath", "subject": "aeloria seated cross-legged, eyes closed, hands on knees, breathing",
         "caption_brief": "the breath was always free. we just forgot to use it"},
        {"beat": "restorative pose", "subject": "aeloria folded in a gentle restorative pose, a bolster beneath her",
         "caption_brief": "rest poses count. slowness is the practice, not the failure"},
    ],
    "fitness": [
        {"beat": "dawn run", "subject": "aeloria mid dawn run, breath visible, trail shoes, steady effort",
         "caption_brief": "i run from nothing and toward nothing — that's the whole point"},
        {"beat": "bodyweight set", "subject": "aeloria mid push-up, focused, no mirror, natural light",
         "caption_brief": "no mirror, no metrics — strength that doesn't need a performance"},
        {"beat": "post-workout stretch", "subject": "aeloria stretching after a workout, hands to the sky, easy breath",
         "caption_brief": "recovery isn't weakness — it's how you stay able to come back"},
    ],
    "travel": [
        {"beat": "arrival wander", "subject": "aeloria wandering slowly with a canvas bag, taking in a new street, curious calm",
         "caption_brief": "travel slowly enough and a new city stops being a checklist"},
        {"beat": "cafe corner", "subject": "aeloria at a small cafe table with a coffee and a notebook, watching the street",
         "caption_brief": "the point of the trip was never the landmarks"},
        {"beat": "quiet detail", "subject": "aeloria noticing a small quiet detail — a doorway, a market stall, soft light",
         "caption_brief": "the city everyone photographs isn't the one you'll remember"},
    ],
}

# Aspirational, specific backgrounds (named landmarks + depth), editorial-master
# style — richer than a bare label so the scene reads like a real place.
LOCATION_SCENE = {
    "forest_house": "at her Forest House — moss, ferns and tall misty pines all around, a weathered wooden porch and soft depth of field behind her",
    "tokyo": "on a quiet Tokyo backstreet lined with paper lanterns and blossoming cherry trees, distant softly-bokeh'd neon",
    "paris": "on a sunlit Haussmann Paris street with wrought-iron balconies, a corner cafe and pale stone facades framing the scene",
    "new_york": "on a calm New York morning street of brownstone stoops and fire escapes, golden light raking down the avenue",
    "london": "on a rainy cobbled London side street of red-brick terraces, the warm amber glow of a corner cafe behind her",
}

SEASON_MOOD = {
    "deep_winter": "cold clear winter light, breath visible",
    "late_winter": "pale late-winter light, bare branches",
    "early_spring": "cool spring light, first cherry blossoms",
    "spring": "fresh green spring light",
    "late_spring": "warm golden late-spring light",
    "early_summer": "long soft early-summer light",
    "deep_summer": "hazy warm midsummer light",
    "late_summer": "golden late-summer light",
    "early_autumn": "amber early-autumn light, leaves turning",
    "autumn": "moody grey autumn light, wet leaves",
    "late_autumn": "muted late-autumn light, mist rising",
    "winter": "cozy low winter light, soft and quiet",
}

_NEUTRAL_SCENE = "outdoors in nature"
_NEUTRAL_MOOD = "soft natural light"


def beat_for_chapter(pillar: str, location: str, season: str, rotation_index: int) -> dict:
    """Assemble a beat for a calendar chapter: a location-neutral pillar subject
    placed into a location + season. Unknown pillar -> slow_living; unknown
    location/season -> neutral descriptor. Never raises."""
    entries = PILLAR_BEATS.get(pillar) or PILLAR_BEATS["slow_living"]
    base = entries[rotation_index % len(entries)]
    scene = LOCATION_SCENE.get(location, _NEUTRAL_SCENE)
    mood = SEASON_MOOD.get(season, _NEUTRAL_MOOD)
    return {
        "beat": base["beat"],
        "prompt_seed": f"{base['subject']} {scene}, {mood}",
        "caption_brief": base["caption_brief"],
    }