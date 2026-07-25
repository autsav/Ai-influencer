"""Named episodic series (return-viewer driver). Series definitions live in
persona/series.yaml; episode numbers are derived from existing briefs so the
counter is idempotent under re-runs."""
from pathlib import Path

import yaml

DEFAULT_YAML = Path(__file__).parent.parent / "persona" / "series.yaml"


def load_series(path: str | None = None) -> list[dict]:
    p = Path(path) if path else DEFAULT_YAML
    try:
        data = yaml.safe_load(p.read_text())
    except (OSError, yaml.YAMLError):
        return []
    return (data or {}).get("series", []) or []


def next_episode(db, slug: str) -> int:
    rows = db.select_all("briefs")
    return sum(1 for r in rows if r.get("series") == slug) + 1


def assign_series(brief: dict, series: dict, db) -> dict:
    n = next_episode(db, series["slug"])
    title = series["title_template"].format(n=n)
    return {**brief, "series": series["slug"], "series_title": title}
