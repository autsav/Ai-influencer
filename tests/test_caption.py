from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.caption import CaptionError, write_caption
from aeloria.persona.loader import load_persona


def _settings(key="sk-test"):
    s = MagicMock()
    s.anthropic_api_key = key
    s.caption_ai_disclosure = False  # off by default in tests; a dedicated test covers it on
    return s


BRIEF = {"beat": "morning tea on the porch", "caption_brief": "gentle anti-hustle take"}


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_write_caption_happy_path(mock_cls):
    client = mock_cls.return_value
    client.messages.create.return_value.content = [MagicMock(text="  slow mornings win.  ")]
    cap = write_caption(load_persona(), BRIEF, settings=_settings())
    assert cap == "slow mornings win."
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    assert "morning tea on the porch" in kwargs["messages"][0]["content"]


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_empty_caption_raises(mock_cls):
    mock_cls.return_value.messages.create.return_value.content = [MagicMock(text="   ")]
    with pytest.raises(CaptionError):
        write_caption(load_persona(), BRIEF, settings=_settings())


def test_missing_api_key_raises():
    with pytest.raises(CaptionError):
        write_caption(load_persona(), BRIEF, settings=_settings(key=""))


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_caption_appends_hashtags_when_plan_given(mock_cls):
    client = mock_cls.return_value
    client.messages.create.return_value.content = [MagicMock(text="slow mornings win.")]
    plan = {"hashtags": ["#slowliving", "#forestlife", "#wellness"]}
    cap = write_caption(load_persona(), BRIEF, settings=_settings(), distribution_plan=plan)
    assert cap.endswith("#slowliving #forestlife #wellness")


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_caption_unchanged_when_no_plan(mock_cls):
    client = mock_cls.return_value
    client.messages.create.return_value.content = [MagicMock(text="slow mornings win.")]
    cap = write_caption(load_persona(), BRIEF, settings=_settings())
    assert cap == "slow mornings win."


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_caption_unchanged_when_plan_has_no_hashtags(mock_cls):
    client = mock_cls.return_value
    client.messages.create.return_value.content = [MagicMock(text="slow mornings win.")]
    cap = write_caption(load_persona(), BRIEF, settings=_settings(), distribution_plan={"hashtags": []})
    assert cap == "slow mornings win."


def _persona():
    p = MagicMock()
    p.voice = {"tone": "warm", "caption_rules": ["no hashtags in body"]}
    p.wedge.voice_pov = "first person"
    return p


def _brief():
    return {"beat": "slow morning", "caption_brief": "a quiet note"}


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_cta_kind_injected_into_prompt(mock_anthropic):
    msg = MagicMock()
    msg.content = [MagicMock(text="a calm caption")]
    mock_anthropic.return_value.messages.create.return_value = msg
    out = write_caption(_persona(), _brief(), settings=_settings(), cta_kind="save")
    assert out == "a calm caption"
    system = mock_anthropic.return_value.messages.create.call_args.kwargs["system"]
    from aeloria.generation.caption import CTA_INSTRUCTIONS
    assert CTA_INSTRUCTIONS["save"] in system


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_cta_none_adds_no_cta_instruction(mock_anthropic):
    msg = MagicMock()
    msg.content = [MagicMock(text="pure vibe")]
    mock_anthropic.return_value.messages.create.return_value = msg
    out = write_caption(_persona(), _brief(), settings=_settings(), cta_kind="none")
    system = mock_anthropic.return_value.messages.create.call_args.kwargs["system"]
    from aeloria.generation.caption import CTA_INSTRUCTIONS
    assert CTA_INSTRUCTIONS["save"] not in system
    assert CTA_INSTRUCTIONS["share"] not in system
    assert out == "pure vibe"


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_hook_framework_in_system_prompt(mock_cls):
    from aeloria.generation.caption import _HOOK_FRAMEWORK
    mock_cls.return_value.messages.create.return_value.content = [MagicMock(text="x")]
    write_caption(load_persona(), BRIEF, settings=_settings())
    system = mock_cls.return_value.messages.create.call_args.kwargs["system"]
    assert _HOOK_FRAMEWORK in system  # viral 1.5s-hook framework baked into every caption


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_framework_and_catchphrase_rotate_into_prompt(mock_cls):
    from aeloria.generation.caption import _CAPTION_FRAMEWORKS
    mock_cls.return_value.messages.create.return_value.content = [MagicMock(text="c")]
    write_caption(load_persona(), {"beat": "b", "caption_brief": "cb", "id": "cap-xyz"},
                  settings=_settings())
    system = mock_cls.return_value.messages.create.call_args.kwargs["system"]
    assert any(fw in system for fw in _CAPTION_FRAMEWORKS)   # a framework is injected
    # a catchphrase from the rotating set is offered
    assert any(c in system for c in load_persona().voice["catchphrases"])


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_user_prompt_carries_narrative_location_trend(mock_cls):
    mock_cls.return_value.messages.create.return_value.content = [MagicMock(text="c")]
    brief = {"beat": "cafe", "caption_brief": "cb", "caption_angle": "the reveal morning",
             "emotional_beat": "proud", "narrative_note": "the nook is finally done",
             "location": "tokyo", "id": "n1"}
    write_caption(load_persona(), brief, settings=_settings(),
                  distribution_plan={"active_trend": "the 'quiet luxury morning' audio"})
    user = mock_cls.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "proud" in user and "the nook is finally done" in user
    assert "tokyo" in user.lower() and "quiet luxury morning" in user
    assert "the reveal morning" in user   # caption_angle preferred over caption_brief


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_disclosure_off_by_default(mock_cls):
    from aeloria.config import get_settings
    mock_cls.return_value.messages.create.return_value.content = [MagicMock(text="slow mornings win.")]
    # a real settings object (not the test _settings that forces it off) -> uses the new default
    cap = write_caption(load_persona(), {"beat": "b", "caption_brief": "cb"}, settings=get_settings())
    from aeloria.generation.caption import AI_DISCLOSURE
    assert AI_DISCLOSURE not in cap


@patch("aeloria.generation.caption.anthropic.Anthropic")
def test_ai_disclosure_appended_after_hashtags_when_enabled(mock_cls):
    from aeloria.generation.caption import AI_DISCLOSURE
    client = mock_cls.return_value
    client.messages.create.return_value.content = [MagicMock(text="slow mornings win.")]
    s = _settings()
    s.caption_ai_disclosure = True
    cap = write_caption(load_persona(), BRIEF, settings=s,
                        distribution_plan={"hashtags": ["#slowliving"]})
    assert cap.endswith(AI_DISCLOSURE)                 # disclosure is the last thing
    assert cap.index("#slowliving") < cap.index(AI_DISCLOSURE)  # after the hashtags
