"""Influencer-life activity system: a rich day-in-the-life library that
supersedes the narrow PILLAR_BEATS. Deterministic + $0; degrades to [] (and the
caller to PILLAR_BEATS) when the yaml is missing. The no-repeat window and
previous-value avoidance read persisted brief state."""
from pathlib import Path

import yaml

DEFAULT_ACT = Path(__file__).parent.parent / "persona" / "activities.yaml"
DEFAULT_CAST = Path(__file__).parent.parent / "persona" / "cast.yaml"

# category -> existing pillar value, so briefs.pillar is never null (optimizer untouched).
CATEGORY_PILLAR = {
    "get_ready": "self_healing", "style": "self_healing", "home": "slow_living",
    "wellness": "self_healing", "hobby": "slow_living", "fitness": "fitness",
    "food": "slow_living", "work": "slow_living", "errands": "travel",
    "social": "travel", "travel": "travel", "pet": "slow_living",
}

_ALL_TIMES = ["dawn", "morning_indoor", "midday", "golden", "dusk", "night", "artificial"]
_ALLOWED_TIMES = {
    "social": ["night", "dusk"],
    "get_ready": ["morning_indoor", "artificial"],
    "style": ["morning_indoor", "artificial", "midday"],
    "fitness": ["midday", "morning_indoor"],
    "food": ["morning_indoor", "golden", "midday"],
    "home": ["morning_indoor", "golden", "midday", "artificial"],
    "wellness": ["morning_indoor", "golden", "artificial"],
    "errands": ["midday", "golden", "morning_indoor"],
    "travel": ["golden", "midday", "dusk"],
    "hobby": ["morning_indoor", "golden", "midday"],
    "pet": ["morning_indoor", "golden", "midday"],
    "work": ["morning_indoor", "artificial", "midday"],
}
_TIME_PHRASE = {
    "dawn": "in soft dawn light", "morning_indoor": "in bright soft morning light indoors",
    "midday": "in clear midday light", "golden": "in warm golden-hour light",
    "dusk": "at dusk in fading blue light", "night": "at night under artificial light",
    "artificial": "under warm indoor lamplight",
}


def time_phrase(tod: str) -> str:
    return _TIME_PHRASE.get(tod, "in natural light")


def _load(path, default, key):
    try:
        data = yaml.safe_load(Path(path or default).read_text())
    except (OSError, yaml.YAMLError):
        return []
    return (data or {}).get(key, []) or []


def load_activities(path=None) -> list[dict]:
    return [a for a in _load(path, DEFAULT_ACT, "activities") if a.get("subjects")]


def load_cast(path=None) -> list[dict]:
    return _load(path, DEFAULT_CAST, "cast")


def _fits(act, location, is_travel, season) -> bool:
    fl = act.get("fits_locations", "anywhere")
    if fl == "home_only" and location != "forest_house":
        return False
    if fl in ("city_only", "travel_only") and not is_travel:
        return False
    fs = act.get("fits_seasons") or []
    return (not fs) or (season in fs)


def eligible(activities, chapter, recent) -> list[dict]:
    location = chapter.get("location", "forest_house")
    is_travel = location != "forest_house"
    season = chapter.get("season", "")
    base = [a for a in activities if _fits(a, location, is_travel, season)]
    if not base:
        return activities  # nothing fits (misconfig) — never crash
    # progressive relax of the no-repeat window: (activity N, category M)
    for na, mc in ((14, 3), (7, 3), (0, 3), (0, 1), (0, 0)):
        ra = {r.get("activity") for r in recent[-na:]} if na else set()
        rc = {r.get("activity_category") for r in recent[-mc:]} if mc else set()
        out = [a for a in base if a["id"] not in ra and a.get("category") not in rc]
        if out:
            return out
    return base


def _signal_gate(elig, activities, recent, window=10):
    # window=10 so `frac` quantizes to tenths and the neutral band is reachable:
    # too many recent signal shots (>=0.30) -> drop signal; too few (<=0.10) ->
    # force signal; a mid fraction (e.g. 0.2) leaves the pool unconstrained.
    by = {a["id"]: a for a in activities}
    sig = [bool(by.get(r.get("activity"), {}).get("signal")) for r in recent[-window:] if r.get("activity")]
    frac = (sum(sig) / len(sig)) if sig else 0.2
    if frac >= 0.30:
        return [a for a in elig if not a.get("signal")] or elig
    if frac <= 0.10:
        return [a for a in elig if a.get("signal")] or elig
    return elig


# Cast types tied to the Forest House world — never travel with her.
_HOME_BOUND_CAST = {"pet", "vehicle", "home", "place"}


def _pick_cast(act_id, cast, h, is_travel=False):
    for c in cast:
        # home-bound cast (dog, car, house, named home café) can't appear abroad.
        if is_travel and c.get("type") in _HOME_BOUND_CAST:
            continue
        if act_id in (c.get("hooks") or []):
            if (h % 100) < round(float(c.get("frequency", 0)) * 100):
                return c.get("appearance")
    return None


def choose_activity(activities, cast, chapter, recent, content_format, h) -> dict:
    is_travel = chapter.get("location", "forest_house") != "forest_house"
    elig = eligible(activities, chapter, recent)
    elig = _signal_gate(elig, activities, recent)
    # soft format affinity
    aff = [a for a in elig if content_format in (a.get("format_affinity") or [content_format])]
    pool = aff or elig
    # category weights (fall back to flat)
    cw = chapter.get("category_weights") or {}
    weighted = []
    for a in pool:
        weighted += [a] * max(1, int(cw.get(a.get("category"), 1)))
    act = weighted[h % len(weighted)]
    subject = act["subjects"][(h // 3) % len(act["subjects"])]
    # time-of-day, avoiding the immediately-previous brief's value
    allowed = _ALLOWED_TIMES.get(act.get("category"), _ALL_TIMES)
    prev = next((r.get("time_of_day") for r in reversed(recent) if r.get("time_of_day")), None)
    times = [t for t in allowed if t != prev] or allowed
    tod = times[(h // 5) % len(times)]
    return {
        "activity": act["id"], "category": act.get("category"),
        "subject": subject, "setting": act.get("setting", ""),
        "mood": act.get("mood", ""), "style_hint": act.get("style_hint", "any"),
        "time_of_day": tod, "pillar": CATEGORY_PILLAR.get(act.get("category"), "slow_living"),
        "indoor": bool(act.get("indoor")),
        "cast_element": _pick_cast(act["id"], cast, h // 7, is_travel),
    }
