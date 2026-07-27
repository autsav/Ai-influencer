"""Strategic calendar: date -> chapter lookups. Pure, yaml-backed. Degrades to
DEFAULT_CHAPTER (a London home office month) when the calendar is missing/malformed."""
from pathlib import Path

import yaml

DEFAULT_YAML = Path(__file__).parent.parent / "persona" / "calendar.yaml"

_PILLARS = ("ai_workflows", "ai_tools", "case_studies", "founder_lifestyle", "future_of_business")

DEFAULT_CHAPTER = {
    "month": 0, "location": "london_home", "season": "autumn",
    "theme": "The build",
    "pillar_weights": {"ai_workflows": 4, "ai_tools": 2, "case_studies": 2, "founder_lifestyle": 2, "future_of_business": 0},
    "series": "workflow-wednesdays", "moments": [],
}


def load_calendar(path: str | None = None) -> dict:
    p = Path(path) if path else DEFAULT_YAML
    try:
        data = yaml.safe_load(p.read_text())
    except (OSError, yaml.YAMLError):
        return {}
    out = {}
    for ch in (data or {}).get("chapters", []) or []:
        m = ch.get("month")
        if isinstance(m, int):
            out[m] = ch
    return out


def active_chapter(d, path: str | None = None) -> dict:
    return load_calendar(path).get(d.month, DEFAULT_CHAPTER)


def pillar_cycle(chapter: dict) -> list[str]:
    weights = chapter.get("pillar_weights") or {}
    buckets = {p: [p] * int(weights.get(p, 0)) for p in _PILLARS}
    cycle = []
    while any(buckets.values()):
        for p in _PILLARS:
            if buckets[p]:
                cycle.append(buckets[p].pop())
    return cycle or ["ai_workflows"]


def active_moment(d, chapter: dict) -> dict | None:
    for mo in chapter.get("moments", []) or []:
        if mo.get("day") == d.day:
            return mo
    return None