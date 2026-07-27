"""Tests for prompt_builder.py — Soul 2.0 clean architecture.

Validates:
  - Backstory/lore NEVER appears in prompts
  - Physical appearance ONLY from visual_dna
  - Scene/wardrobe/mood from user overrides
  - All three styles (film_editorial, flash_candid, paparazzi_night) work
  - Deterministic per-brief hash
  - Mood biases expression
"""
import hashlib as _hl

import pytest

from aeloria.generation.prompt_builder import (
    build_prompt,
    _choose_style,
    _FILMS,
    _POSSIBLE_POSES,
    _POSSIBLE_EXPRESSIONS,
    _POSSIBLE_PROPS,
    _POSSIBLE_HAIR,
    _POSSIBLE_OUTFITS,
    _FILM_ANGLES,
    _FLASH_ANGLES,
    _PAP_ANGLES,
)
from aeloria.persona.loader import load_persona


def _h(brief: dict) -> int:
    key = str(brief.get("id") or brief.get("prompt_seed", ""))
    return int(_hl.md5(key.encode()).hexdigest(), 16)


def _film_brief(p):
    for i in range(200):
        b = {"prompt_seed": f"scene {i}"}
        if _choose_style(_h(b), "") == "film_editorial":
            return b, build_prompt(p, b)
    raise AssertionError("no film brief found")


def _flash_brief(p):
    for i in range(200):
        b = {"prompt_seed": f"scene {i}", "pillar": "case_studies"}
        if _choose_style(_h(b), "case_studies") == "flash_candid":
            return b, build_prompt(p, b)
    raise AssertionError("no flash brief found")


def _pap_brief(p):
    for i in range(200):
        b = {"prompt_seed": f"scene {i}", "pillar": "case_studies"}
        if _choose_style(_h(b), "case_studies") == "paparazzi_night":
            return b, build_prompt(p, b)
    raise AssertionError("no paparazzi brief found")


# ── Soul 2.0: backbone invariants ─────────────────────────────────────────────

def test_core_identity_in_all_styles(persona):
    for _, prompt in (_film_brief(persona), _flash_brief(persona), _pap_brief(persona)):
        assert "aeloria" in prompt
        assert "clearly adult woman" in prompt
        assert "auburn" in prompt  # from visual_dna
        assert "green" in prompt    # from visual_dna
        assert "visible pores" in prompt
        assert "peach fuzz" in prompt
        assert "no beauty filter" in prompt
        assert "Expression:" in prompt
        assert "color palette" in prompt or "#" in prompt  # grade
        assert "Avoid:" in prompt
        assert "Do not change her facial features" in prompt
        assert any(f in prompt for f in _FILMS)


def test_physical_appearance_only_not_backstory(persona):
    """Soul 2.0: backbone NEVER encodes backstory/lore."""
    prompt = build_prompt(persona, {"prompt_seed": "cafe in London"})
    # Backstory words must NOT appear
    forbidden = [
        "forest house", "cabin", "creek", "porch", "woodland",
        "wooden spoon", "mossy", "old-growth", "morning tea",
        "creek bank", "treeline", "cabin porch", "the leaking roof",
    ]
    found = [w for w in forbidden if w in prompt.lower()]
    assert not found, f"Backstory leaked into prompt: {found}"


def test_wardrobe_override_replaces_outfit_pool(persona):
    """User-provided wardrobe must appear verbatim in prompt."""
    prompt = build_prompt(persona, {
        "prompt_seed": "a woman in a red dress",
        "wardrobe": "a red off-the-shoulder polka-dot maxi dress",
    })
    assert "red off-the-shoulder polka-dot maxi dress" in prompt


def test_location_override_appears_in_prompt(persona):
    """User-provided location must appear in prompt."""
    prompt = build_prompt(persona, {
        "prompt_seed": "aeloria",
        "location": "standing on Westminster Bridge with Big Ben visible",
    })
    assert "westminster" in prompt.lower()


def test_mood_override_replaces_pillar_mood(persona):
    """mood_override must appear and supersede pillar mood."""
    prompt = build_prompt(persona, {
        "prompt_seed": "morning walk",
        "mood_override": "serene and contemplative",
        "pillar": "founder_lifestyle",
    })
    assert "serene and contemplative" in prompt
    # founder_lifestyle pillar mood should NOT appear (mood_override takes precedence)
    assert "approachable" not in prompt.lower()


def test_mood_override_with_location_both_present(persona):
    """mood_override + location both appear when both are provided."""
    prompt = build_prompt(persona, {
        "prompt_seed": "london afternoon",
        "location": "Westminster Bridge",
        "mood_override": "warm golden hour glow",
    })
    assert "westminster" in prompt.lower()
    assert "golden hour" in prompt.lower()


def test_camera_override_replaces_style_default(persona):
    """camera_override must replace the style's default camera."""
    prompt = build_prompt(persona, {
        "prompt_seed": "portrait",
        "camera_override": "shot on Leica M6, Tri-X 400 film",
    })
    assert "leica" in prompt.lower()


def test_style_override_forces_style(persona):
    """style_override must force the correct style regardless of pillar."""
    for hint in ("candid", "editorial", "paparazzi"):
        prompt = build_prompt(persona, {
            "prompt_seed": "scene",
            "style_override": hint,
            "pillar": "ai_workflows",
        })
        if hint == "candid":
            assert prompt.startswith("A raw flash-lit candid snapshot")
        elif hint == "editorial":
            assert prompt.startswith("A candid fashion photograph")


# ── Style markers ──────────────────────────────────────────────────────────────

def test_film_editorial_opener():
    p = load_persona()
    _, prompt = _film_brief(p)
    assert prompt.startswith("A candid fashion photograph shot on a 50mm lens")
    assert "raw unretouched look" in prompt
    for bad in ("8k", "photorealistic", "high-end retouch"):
        assert bad not in prompt.lower()


def test_flash_candid_opener():
    p = load_persona()
    _, prompt = _flash_brief(p)
    assert prompt.startswith("A raw flash-lit candid snapshot")
    assert "flash" in prompt
    assert "chemical dust" in prompt
    assert "vignette" in prompt
    assert "disposable-camera" in prompt


def test_paparazzi_opener():
    p = load_persona()
    _, prompt = _pap_brief(p)
    assert prompt.startswith("A low-light candid paparazzi-style night photograph")
    assert "paparazzi" in prompt
    assert "#" in prompt  # hex color grade


def test_paparazzi_camera_and_grade_vary():
    p = load_persona()
    cams, grades = set(), set()
    for i in range(300):
        bid = f"pv-{i}"
        if _choose_style(int(_hl.md5(bid.encode()).hexdigest(), 16), "case_studies") == "paparazzi_night":
            pr = build_prompt(p, {"id": bid, "pillar": "case_studies", "prompt_seed": "night street"})
            for cam in ("telephoto lens", "moderate lens", "fisheye", "film camera"):
                if cam in pr:
                    cams.add(cam)
            import re
            m = re.search(r"\(#[0-9a-f, #]+\)", pr)
            if m:
                grades.add(m.group())
    assert len(cams) >= 3 and len(grades) >= 5


# ── Hash determinism ─────────────────────────────────────────────────────────

def test_deterministic_same_brief():
    p = load_persona()
    b = {"id": "b1", "prompt_seed": "london morning"}
    assert build_prompt(p, b) == build_prompt(p, b)


def test_different_seeds_produce_different_prompts():
    p = load_persona()
    prompts = {build_prompt(p, {"prompt_seed": f"s {i}"}) for i in range(40)}
    assert len(prompts) >= 15


def test_combination_space_sufficient():
    combos = (
        len(_POSSIBLE_POSES) * len(_POSSIBLE_EXPRESSIONS)
        * len(_POSSIBLE_PROPS) * len(_POSSIBLE_HAIR)
        * len(_POSSIBLE_OUTFITS) * len(_FILMS)
        * (len(_FILM_ANGLES) + len(_FLASH_ANGLES))
    )
    assert combos > 1_000_000


# ── Pillar mood ───────────────────────────────────────────────────────────────

def test_pillar_mood_when_no_override():
    p = load_persona()
    # pillar mood should appear when no mood_override is set
    prompt = build_prompt(p, {"prompt_seed": "run", "pillar": "founder_lifestyle"})
    assert "approachable" in prompt or "confident" in prompt.lower()

    prompt = build_prompt(p, {"prompt_seed": "flow", "pillar": "ai_workflows"})
    assert "focused" in prompt or "determination" in prompt.lower()


def test_style_bias_by_pillar():
    case_studies = sum(_choose_style(i, "case_studies") == "flash_candid" for i in range(300))
    home = sum(_choose_style(i, "founder_lifestyle") == "flash_candid" for i in range(300))
    assert case_studies >= home


# ── Expression mood bias ──────────────────────────────────────────────────────

def test_mood_biases_expression():
    p = load_persona()
    det = build_prompt(p, {"prompt_seed": "gym set", "mood": "determined"})
    assert "Expression:" in det
    assert any(w in det for w in ("confidence", "confident", "grin", "laugh", "mischievous"))


def test_determined_mood_avoids_dreamy():
    p = load_persona()
    det = build_prompt(p, {"prompt_seed": "gym set", "mood": "determined"})
    # dreamy expressions should NOT dominate determined mood
    dreamy_count = sum(w in det.lower() for w in ("dreamy", "eyes closed", "serene"))
    active_count = sum(w in det.lower() for w in ("confident", "direct", "smirk", "focused"))
    assert active_count >= dreamy_count


# ── Aesthetic variants ────────────────────────────────────────────────────────

def test_aesthetic_variants_are_occasional():
    p = load_persona()
    prompts = [build_prompt(p, {"prompt_seed": f"scene {i}", "id": f"v{i}"}) for i in range(80)]
    pov = sum("first-person POV" in pr for pr in prompts)
    nost = sum(("Y2K" in pr or "90s film" in pr or "70s film" in pr) for pr in prompts)
    assert pov >= 1 and nost >= 1
    assert (pov + nost) < len(prompts) * 0.4


# ── Skin realism ──────────────────────────────────────────────────────────────

def test_skin_block_high_fidelity():
    p = load_persona()
    prompt = build_prompt(p, {"prompt_seed": "portrait", "id": "skin-1"})
    assert "visible pores" in prompt and "peach fuzz" in prompt
    for marker in ("vellus", "T-zone", "flyaway"):
        assert marker in prompt


# ── City mode ─────────────────────────────────────────────────────────────────

def test_city_mode_uses_city_angles_not_forest():
    p = load_persona()
    prompt = build_prompt(p, {
        "prompt_seed": "london afternoon",
        "location": "Westminster Bridge with Big Ben visible",
    })
    # Must have city angle
    assert any(city_word in prompt.lower() for city_word in ["westminster", "london", "borough", "shoreditch", "embankment"])
    # Must NOT have forest in the angle/atmosphere lines
    import re
    angle_match = re.search(r"candid fashion photograph[.,].*?\. Scene:", prompt, re.I)
    angle_text = angle_match.group() if angle_match else ""
    forest_words = re.findall(r"\b(forest|creek|cabin|woodland)\b", angle_text, re.I)
    assert not forest_words, f"Forest words in angle: {forest_words}"


def test_no_london_without_location():
    p = load_persona()
    prompt = build_prompt(p, {"prompt_seed": "cafe morning"})
    # No city landmarks should appear without explicit location
    assert "westminster" not in prompt.lower()
    assert "borough market" not in prompt.lower()


# ── Backstory: Soul ID isolation ───────────────────────────────────────────────

def test_backstory_not_in_prompt():
    """Verify backstory lore never leaks into prompts."""
    p = load_persona()
    backstory_phrases = [
        "forest house", "old-growth", "leaking roof", "woodpecker",
        "mossy trail", "east window at golden hour", "cabin kitchen",
        "the build", "coworking space", "tech conference",
    ]
    for phrase in backstory_phrases:
        for seed in ["cafe", "london", "beach", "desk", "run"]:
            prompt = build_prompt(p, {"prompt_seed": seed})
            assert phrase.lower() not in prompt.lower(), f"'{phrase}' found in prompt for seed '{seed}'"


# ── conftest fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def persona():
    return load_persona()
