from unittest.mock import MagicMock, patch

from aeloria.showrunner.briefing import DAILY_BRIEFING_PROMPT, enrich_brief


def _settings(enabled, key="sk"):
    s = MagicMock(); s.briefing_enabled = enabled; s.anthropic_api_key = key
    return s


def test_prompt_deliverable_mentions_the_outputs():
    for token in ("SCENE_SEED", "EMOTIONAL_BEAT", "NARRATIVE_NOTE", "CAPTION_ANGLE"):
        assert token in DAILY_BRIEFING_PROMPT


def test_enrich_disabled_is_passthrough():
    seed, cap, angle = enrich_brief("scene", "cap brief", "proud", "the reveal",
                                    MagicMock(), _settings(False))
    assert seed == "scene" and cap == "cap brief" and angle == "the reveal"


@patch("aeloria.showrunner.briefing.anthropic.Anthropic")
def test_enrich_enabled_calls_haiku(mock_cls):
    import json
    mock_cls.return_value.messages.create.return_value.content = [
        MagicMock(text=json.dumps({"scene_seed": "S", "caption_brief": "C", "caption_angle": "A"}))]
    seed, cap, angle = enrich_brief("scene", "cb", "proud", "the reveal",
                                    MagicMock(voice={}, wedge=MagicMock(voice_pov="pov")), _settings(True))
    assert (seed, cap, angle) == ("S", "C", "A")


@patch("aeloria.showrunner.briefing.anthropic.Anthropic", side_effect=Exception("down"))
def test_enrich_llm_failure_falls_back(_m):
    seed, cap, angle = enrich_brief("scene", "cb", "proud", "note", MagicMock(), _settings(True))
    assert seed == "scene" and angle == "note"   # passthrough on failure
