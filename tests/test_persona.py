import pytest

from aeloria.persona.loader import PersonaError, load_persona


def test_load_default_bible():
    """aeloria.yaml loads as a clean Soul 2.0 spec — no lore embedded."""
    p = load_persona()
    assert p.identity["name"] == "Aeloria"
    # wedge is now empty (lore lives in backstory.yaml)
    assert p.wedge.world == ""
    assert p.wedge.reel_format == ""
    assert p.wedge.voice_pov == ""
    # visual_dna is the Soul 2.0 appearance spec
    assert p.visual_dna["hair"] == "auburn, usually in a loose high bun, escaping strands"
    assert p.visual_dna["eyes"] == "green"
    assert "freckles" in p.visual_dna["skin"]
    assert "visible pores" in p.visual_dna["skin"]
    assert p.niches.core.startswith("wellness")
    assert len(p.hard_rules) >= 4
    # Mannerisms are now top-level (moved from character block)
    assert len(p.mannerisms) == 5
    assert "pushing hair back from her face" in p.mannerisms[0]


def test_missing_wedge_is_not_fatal(tmp_path):
    """Wedge is optional — lore lives in backstory.yaml now."""
    minimal = tmp_path / "minimal.yaml"
    minimal.write_text(
        "identity:\n  name: Test\n"
        "visual_dna:\n  hair: brown\n  eyes: brown\n  skin: fair\n"
        "voice:\n  caption_rules: []\n"
        "niches:\n  core: x\n  secondary: y\n"
        "hard_rules: []\n"
    )
    # Should NOT raise — wedge is optional
    p = load_persona(str(minimal))
    assert p.identity["name"] == "Test"
    assert p.wedge.world == ""


def test_persona_exposes_mannerisms_and_expression():
    """Soul 2.0: mannerisms/expression at top level, not in character block."""
    p = load_persona()
    assert len(p.mannerisms) >= 5
    assert all(isinstance(m, str) and m for m in p.mannerisms)
    assert len(p.expression_repertoire) >= 8
    joined = " ".join(p.expression_repertoire).lower()
    assert any(cue in joined for cue in ("smile", "grin", "laugh", "bothered"))


def test_backstory_yaml_not_loaded_in_persona():
    """backstory.yaml is NOT loaded by load_persona — only aeloria.yaml is."""
    p = load_persona()
    # Backstory fields must NOT appear in the persona loaded for generation
    assert p.wedge.world == ""
    # character block is now minimal (no backstory, no relationships)
    assert p.character.get("backstory") is None
    assert p.character.get("relationships") is None
