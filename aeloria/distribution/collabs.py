# aeloria/distribution/collabs.py
"""Adjacent-accounts list for duets/stitches/targeted comments. Curated in
persona/collabs.yaml; consumed by the engagement worker (Phase 5a)."""
from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).parent.parent / "persona" / "collabs.yaml"

# niche keys we match on (subset of seo.NICHE_TAGS keys)
NICHE_KEYS = ["wellness", "fitness", "travel", "gaming"]


def load(path: str | None = None) -> list[dict]:
    p = Path(path) if path else DEFAULT_PATH
    try:
        data = yaml.safe_load(p.read_text())
    except (OSError, yaml.YAMLError):
        return []
    if not data:
        return []
    return list(data.get("collabs", []))


def match(entries: list[dict], niche: str) -> list[dict]:
    """Return entries whose niches overlap the niche label.
    niche is a free-text label like 'wellness + nature (slow living, forest life)';
    we match if any NICHE_KEY is a substring of the label AND in the entry's niches."""
    label = (niche or "").lower()
    wanted = {k for k in NICHE_KEYS if k in label}
    if not wanted:
        return []
    out = []
    for e in entries:
        if wanted & {n.lower() for n in e.get("niches", [])}:
            out.append(e)
    return out