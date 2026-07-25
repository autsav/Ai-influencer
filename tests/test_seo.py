from unittest.mock import MagicMock

from aeloria.distribution.seo import build
from aeloria.persona.loader import load_persona


PERSONA = load_persona()


def _brief(beat="morning tea on the porch", slot_type="reel"):
    return {"beat": beat, "caption_brief": "slow living", "slot_type": slot_type}


def test_hashtags_returns_3_to_5():
    res = build(PERSONA, _brief())
    assert 3 <= len(res["hashtags"]) <= 5


def test_hashtags_are_lowercased_deduped_no_wall():
    res = build(PERSONA, _brief())
    tags = res["hashtags"]
    assert all(t.startswith("#") for t in tags)
    assert len(tags) == len(set(tags))
    assert all(t == t.lower() for t in tags)


def test_hashtags_relevant_to_wellness_niche():
    res = build(PERSONA, _brief("forest trail run at dawn", "reel"))
    # wellness/forest words should surface a nature or slow-living tag
    joined = " ".join(res["hashtags"]).lower()
    assert any(k in joined for k in ("nature", "forest", "slow", "wellness", "trail"))


def test_on_screen_keywords_for_reel():
    res = build(PERSONA, _brief("still cabin window at golden hour", "reel"))
    assert isinstance(res["on_screen_keywords"], list)
    assert 1 <= len(res["on_screen_keywords"]) <= 3


def test_on_screen_keywords_empty_for_static():
    res = build(PERSONA, _brief("porch tea", "static"))
    assert res["on_screen_keywords"] == []


def test_handle_empty_beat():
    res = build(PERSONA, {"beat": "", "caption_brief": "", "slot_type": "reel"})
    assert 3 <= len(res["hashtags"]) <= 5  # niche fallback tags still apply


def test_reel_uses_category_hook_when_activity_category_present():
    from aeloria.distribution.seo import _REEL_HOOKS
    res = build(PERSONA, {"beat": "gym_set", "caption_brief": "fitness moment",
                          "slot_type": "reel", "activity_category": "fitness", "id": "b-fit-1"})
    kws = res["on_screen_keywords"]
    assert len(kws) == 1 and kws[0] in _REEL_HOOKS["fitness"]  # a punchy hook, not raw words


def test_snake_case_activity_beat_yields_real_keywords():
    # Activity beats are snake_case ids; the overlay must read real words,
    # not the raw "travel_sightseeing" compound token.
    res = build(PERSONA, {"beat": "travel_sightseeing",
                          "caption_brief": "travel moment: pausing before a landmark",
                          "slot_type": "reel"})
    kws = res["on_screen_keywords"]
    assert "travel" in kws and "sightseeing" in kws
    assert not any("_" in w for w in kws)