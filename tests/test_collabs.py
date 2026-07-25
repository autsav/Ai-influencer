# tests/test_collabs.py
from aeloria.distribution.collabs import load, match

import aeloria.distribution.collabs as collabs_mod

ENTRIES = [
    {"handle": "@forestmeditations", "platform": "instagram", "niches": ["wellness"], "kind": "comment"},
    {"handle": "@trailrunnerdaily", "platform": "instagram", "niches": ["fitness"], "kind": "duet"},
    {"handle": "@cabindiaries", "platform": "instagram", "niches": ["wellness", "travel"], "kind": "stitch"},
]


def test_match_filters_by_wellness():
    res = match(ENTRIES, "wellness + nature (slow living, forest life)")
    handles = [e["handle"] for e in res]
    assert "@forestmeditations" in handles
    assert "@cabindiaries" in handles
    assert "@trailrunnerdaily" not in handles


def test_match_fitness_only():
    res = match(ENTRIES, "fitness (trail runs, bodyweight, recovery)")
    assert [e["handle"] for e in res] == ["@trailrunnerdaily"]


def test_match_unknown_niche_returns_empty():
    assert match(ENTRIES, "cooking") == []


def test_load_missing_file_returns_empty(tmp_path, monkeypatch):
    missing = tmp_path / "nope.yaml"
    assert load(str(missing)) == []


def test_load_reads_yaml(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text(
        "collabs:\n"
        "  - handle: '@x'\n"
        "    platform: instagram\n"
        "    niches: ['wellness']\n"
        "    kind: comment\n"
    )
    res = load(str(p))
    assert res == [{"handle": "@x", "platform": "instagram", "niches": ["wellness"], "kind": "comment"}]