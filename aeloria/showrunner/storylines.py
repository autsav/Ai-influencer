"""Recurring story threads. Deterministically advances one flattened (thread, beat)
sequence over days so the feed carries an emotional throughline — $0, no LLM."""
from pathlib import Path

import yaml

DEFAULT = Path(__file__).parent.parent / "persona" / "storylines.yaml"
BEAT_STEP = 2   # each beat lingers this many days before advancing


def load_storylines(path=None) -> list[dict]:
    try:
        data = yaml.safe_load(Path(path or DEFAULT).read_text())
    except (OSError, yaml.YAMLError):
        return []
    return (data or {}).get("storylines", []) or []


def active_storyline(storylines, chapter, day_index) -> dict | None:
    """Pick the active thread+beat for this chapter deterministically. Threads whose
    `location` is neither the chapter location nor "any" are excluded."""
    location = chapter.get("location", "forest_house")
    seq = [(t["id"], i, b)
           for t in storylines if t.get("location") in (location, "any")
           for i, b in enumerate(t.get("beats") or [])]
    if not seq:
        return None
    tid, bi, b = seq[(day_index // BEAT_STEP) % len(seq)]
    return {"thread": tid, "beat_index": bi,
            "note": b.get("note", ""), "emotion": b.get("emotion", "")}
