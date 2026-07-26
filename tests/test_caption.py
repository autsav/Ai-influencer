from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.caption import CaptionError, write_caption
from aeloria.persona.loader import load_persona


def _settings(key="sk-test"):
    s = MagicMock()
    s.caption_ai_disclosure = False
    return s


BRIEF = {"beat": "desk workflow morning", "caption_brief": "AI saves 6 hours every day"}


@patch("aeloria.generation.caption.llm_generate")
def test_write_caption_happy_path(mock_llm):
    mock_llm.return_value = "  slow mornings win.  "
    cap = write_caption(load_persona(), BRIEF, settings=_settings())
    assert cap == "slow mornings win."
    prompt = mock_llm.call_args.args[0]
    assert "desk workflow morning" in prompt


@patch("aeloria.generation.caption.llm_generate")
def test_empty_caption_raises(mock_llm):
    mock_llm.return_value = "   "
    with pytest.raises(CaptionError):
        write_caption(load_persona(), BRIEF, settings=_settings())


@patch("aeloria.generation.caption.llm_generate")
def test_caption_appends_hashtags_when_plan_given(mock_llm):
    mock_llm.return_value = "slow mornings win."
    plan = {"hashtags": ["#AIAutomation", "#AIWorkflow", "#FutureOfWork"]}
    cap = write_caption(load_persona(), BRIEF, settings=_settings(), distribution_plan=plan)
    assert cap.endswith("#AIAutomation #AIWorkflow #FutureOfWork")


@patch("aeloria.generation.caption.llm_generate")
def test_caption_unchanged_when_no_plan(mock_llm):
    mock_llm.return_value = "slow mornings win."
    cap = write_caption(load_persona(), BRIEF, settings=_settings())
    assert cap == "slow mornings win."


@patch("aeloria.generation.caption.llm_generate")
def test_caption_unchanged_when_plan_has_no_hashtags(mock_llm):
    mock_llm.return_value = "slow mornings win."
    cap = write_caption(load_persona(), BRIEF, settings=_settings(), distribution_plan={"hashtags": []})
    assert cap == "slow mornings win."


def _persona():
    p = MagicMock()
    p.voice = {"tone": "warm", "caption_rules": ["no hashtags in body"]}
    p.wedge.voice_pov = "first person"
    return p


def _brief():
    return {"beat": "slow morning", "caption_brief": "a quiet note"}


@patch("aeloria.generation.caption.llm_generate")
def test_cta_kind_injected_into_prompt(mock_llm):
    mock_llm.return_value = "a calm caption"
    out = write_caption(_persona(), _brief(), settings=_settings(), cta_kind="save")
    assert out == "a calm caption"
    prompt = mock_llm.call_args.args[0]
    from aeloria.generation.caption import CTA_INSTRUCTIONS
    assert CTA_INSTRUCTIONS["save"] in prompt


@patch("aeloria.generation.caption.llm_generate")
def test_cta_none_adds_no_cta_instruction(mock_llm):
    mock_llm.return_value = "pure vibe"
    out = write_caption(_persona(), _brief(), settings=_settings(), cta_kind="none")
    prompt = mock_llm.call_args.args[0]
    from aeloria.generation.caption import CTA_INSTRUCTIONS
    assert CTA_INSTRUCTIONS["save"] not in prompt
    assert CTA_INSTRUCTIONS["share"] not in prompt
    assert out == "pure vibe"


@patch("aeloria.generation.caption.llm_generate")
def test_hook_framework_in_system_prompt(mock_llm):
    from aeloria.generation.caption import _HOOK_FRAMEWORK
    mock_llm.return_value = "x"
    write_caption(load_persona(), BRIEF, settings=_settings())
    prompt = mock_llm.call_args.args[0]
    assert _HOOK_FRAMEWORK in prompt


@patch("aeloria.generation.caption.llm_generate")
def test_framework_and_catchphrase_rotate_into_prompt(mock_llm):
    from aeloria.generation.caption import _CAPTION_FRAMEWORKS
    mock_llm.return_value = "c"
    write_caption(load_persona(), {"beat": "b", "caption_brief": "cb", "id": "cap-xyz"},
                  settings=_settings())
    prompt = mock_llm.call_args.args[0]
    assert any(fw in prompt for fw in _CAPTION_FRAMEWORKS)
    assert any(c in prompt for c in load_persona().voice["catchphrases"])


@patch("aeloria.generation.caption.llm_generate")
def test_user_prompt_carries_narrative_location_trend(mock_llm):
    mock_llm.return_value = "c"
    brief = {"beat": "cafe", "caption_brief": "cb", "caption_angle": "the reveal morning",
             "emotional_beat": "proud", "narrative_note": "the nook is finally done",
             "location": "tokyo", "id": "n1"}
    write_caption(load_persona(), brief, settings=_settings(),
                  distribution_plan={"active_trend": "the 'quiet luxury morning' audio"})
    prompt = mock_llm.call_args.args[0]
    assert "proud" in prompt and "the nook is finally done" in prompt
    assert "tokyo" in prompt.lower() and "quiet luxury morning" in prompt
    assert "the reveal morning" in prompt


@patch("aeloria.generation.caption.llm_generate")
def test_disclosure_off_by_default(mock_llm):
    from aeloria.config import get_settings
    mock_llm.return_value = "slow mornings win."
    cap = write_caption(load_persona(), {"beat": "b", "caption_brief": "cb"}, settings=get_settings())
    from aeloria.generation.caption import AI_DISCLOSURE
    assert AI_DISCLOSURE not in cap


@patch("aeloria.generation.caption.llm_generate")
def test_ai_disclosure_appended_after_hashtags_when_enabled(mock_llm):
    from aeloria.generation.caption import AI_DISCLOSURE
    mock_llm.return_value = "slow mornings win."
    s = _settings()
    s.caption_ai_disclosure = True
    cap = write_caption(load_persona(), BRIEF, settings=s,
                        distribution_plan={"hashtags": ["#AIAutomation"]})
    assert cap.endswith(AI_DISCLOSURE)
    assert cap.index("#AIAutomation") < cap.index(AI_DISCLOSURE)