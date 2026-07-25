"""Trend store: curated persona/trends.yaml + runtime `trends` table rows.
Meta Graph API exposes no trending data, so trends are operator-curated."""
from datetime import datetime, timezone
from pathlib import Path

import yaml

from aeloria.distribution.seo import STOPWORDS

DEFAULT_YAML = Path(__file__).parent.parent / "persona" / "trends.yaml"


def _is_expired(expires_at) -> bool:
    if not expires_at:
        return False
    try:
        exp = str(expires_at)
        # accept date-only or full iso
        if "T" not in exp:
            exp = exp + "T00:00:00+00:00"
        dt = datetime.fromisoformat(exp)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return dt < datetime.now(timezone.utc)


def _normalize(row: dict, source: str) -> dict:
    return {
        "id": row.get("id"),          # table row id (None for yaml-sourced trends)
        "kind": row.get("kind"),
        "ref": row.get("ref"),
        "note": row.get("note", "") or "",
        "expires_at": row.get("expires_at"),
        "source": source,
    }


def load_active(yaml_path: str | None, db) -> list[dict]:
    out: list[dict] = []
    p = Path(yaml_path) if yaml_path else DEFAULT_YAML
    try:
        data = yaml.safe_load(p.read_text())
    except (OSError, yaml.YAMLError):
        data = None
    for row in (data or {}).get("trends", []) or []:
        if _is_expired(row.get("expires_at")):
            continue
        out.append(_normalize(row, "yaml"))
    # table rows
    try:
        rows = db.select("trends")
    except Exception:
        rows = []
    for row in rows or []:
        if _is_expired(row.get("expires_at")):
            continue
        out.append(_normalize(row, "table"))
    return out


def _brief_words(brief: dict) -> set[str]:
    text = f"{brief.get('beat', '')} {brief.get('caption_brief', '')}".lower()
    return {w for w in text.split() if w and w not in STOPWORDS}


def match(active: list[dict], brief: dict) -> str | None:
    words = _brief_words(brief)
    for t in active:
        ref_note = f"{t.get('ref', '')} {t.get('note', '')}".lower()
        ref_words = {w for w in ref_note.split() if w and w not in STOPWORDS and not w.startswith("#")}
        if words & ref_words:
            return t.get("ref")
    return None