# tests/test_trends.py
from unittest.mock import MagicMock

from aeloria.distribution.trends import load_active, match


def _yaml(tmp_path, body):
    p = tmp_path / "t.yaml"
    p.write_text(body)
    return str(p)


def test_load_active_merges_yaml_and_table_drops_expired(tmp_path):
    yaml_path = _yaml(tmp_path,
        "trends:\n"
        "  - kind: audio\n"
        "    ref: 'forest-ambient-123'\n"
        "    note: 'forest ambient rising'\n"
        "    expires_at: '2099-01-01'\n"
        "  - kind: hashtag\n"
        "    ref: '#slowliving'\n"
        "    note: 'evergreen slow living'\n"
        "    expires_at: '2020-01-01'\n"  # expired
    )
    db = MagicMock()
    db.select.return_value = [
        {"id": "row-7", "kind": "format", "ref": "still-then-alive", "note": "held still then motion",
         "expires_at": "2099-01-01"},
    ]
    active = load_active(yaml_path, db)
    refs = {t["ref"] for t in active}
    assert "forest-ambient-123" in refs
    assert "still-then-alive" in refs
    assert "#slowliving" not in refs  # expired yaml entry dropped
    # table-sourced trend carries its row id; yaml-sourced has id=None
    by_ref = {t["ref"]: t for t in active}
    assert by_ref["still-then-alive"]["id"] == "row-7"
    assert by_ref["forest-ambient-123"]["id"] is None


def test_load_active_missing_yaml_returns_table_only(tmp_path):
    db = MagicMock()
    db.select.return_value = [{"kind": "audio", "ref": "x", "note": "", "expires_at": "2099-01-01"}]
    active = load_active(str(tmp_path / "nope.yaml"), db)
    assert [t["ref"] for t in active] == ["x"]


def test_load_active_db_failure_returns_yaml_only(tmp_path):
    yaml_path = _yaml(tmp_path,
        "trends:\n  - kind: audio\n    ref: 'y'\n    note: ''\n    expires_at: '2099-01-01'\n")
    db = MagicMock()
    db.select.side_effect = RuntimeError("supabase down")
    active = load_active(yaml_path, db)
    assert [t["ref"] for t in active] == ["y"]


def test_match_returns_ref_on_keyword_overlap():
    active = [
        {"ref": "forest-ambient-123", "note": "forest ambient rising", "kind": "audio"},
        {"ref": "gym-beat-9", "note": "high energy gym", "kind": "audio"},
    ]
    brief = {"beat": "forest trail at dawn", "caption_brief": "ambient calm"}
    assert match(active, brief) == "forest-ambient-123"


def test_match_returns_none_when_no_overlap():
    active = [{"ref": "gym-beat-9", "note": "high energy gym", "kind": "audio"}]
    brief = {"beat": "porch tea", "caption_brief": "slow morning"}
    assert match(active, brief) is None


def test_match_ignores_stopwords():
    active = [{"ref": "the-audio", "note": "the the the", "kind": "audio"}]
    brief = {"beat": "she looks at the window", "caption_brief": ""}
    assert match(active, brief) is None