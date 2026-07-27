# tests/test_collabs.py
from aeloria.distribution.collabs import load, match

import aeloria.distribution.collabs as collabs_mod

ENTRIES = [
    {"handle": "@aitechdaily", "platform": "instagram", "niches": ["ai automation"], "kind": "comment"},
    {"handle": "@workflowbuilder", "platform": "instagram", "niches": ["ai automation", "ai tools"], "kind": "stitch"},
    {"handle": "@founderlife", "platform": "instagram", "niches": ["founder lifestyle"], "kind": "mention"},
]
MATCH_NICHE = "AI automation for business (workflows, tools, case studies)"


def test_match_filters_by_ai_niche():
    res = match(ENTRIES, MATCH_NICHE)
    handles = {e["handle"] for e in res}
    assert "@aitechdaily" in handles
    assert "@workflowbuilder" in handles
    assert "@founderlife" not in handles


def test_match_founder_lifestyle_only():
    res = match(ENTRIES, "founder lifestyle (building, testing, learning, remote work)")
    handles = [e["handle"] for e in res]
    assert handles == ["@founderlife"]


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
        "    niches: ['ai automation']\n"
        "    kind: comment\n"
    )
    res = load(str(p))
    assert res == [{"handle": "@x", "platform": "instagram", "niches": ["ai automation"], "kind": "comment"}]