from unittest.mock import MagicMock, patch

import pytest

from aeloria.engagement.drafter import draft_reply, claims_human, DrafterError


def _persona():
    p = MagicMock()
    p.voice = {"tone": "warm", "caption_rules": []}
    p.wedge.voice_pov = "first person"
    return p


def _settings():
    s = MagicMock()
    s.anthropic_api_key = "key"
    return s


def test_claims_human_detects_assertions():
    assert claims_human("Yes, I'm a real person!")
    assert claims_human("i am human, not a bot")
    assert claims_human("Actually I am a real girl")
    assert claims_human("I'm a living, breathing person")
    assert claims_human("I promise I'm not artificial")
    assert not claims_human("I'm so glad this resonated 🌲")


@patch("aeloria.engagement.drafter.anthropic.Anthropic")
def test_draft_reply_returns_text(mock_anthropic):
    msg = MagicMock()
    msg.content = [MagicMock(text="so glad you felt that 🌲")]
    mock_anthropic.return_value.messages.create.return_value = msg
    out = draft_reply(_persona(), "reply", "love this so calm", settings=_settings())
    assert out == "so glad you felt that 🌲"
    system = mock_anthropic.return_value.messages.create.call_args.kwargs["system"]
    assert "never" in system.lower()  # human-claim rule present in prompt


@patch("aeloria.engagement.drafter.anthropic.Anthropic")
def test_draft_reply_blocks_human_claim(mock_anthropic):
    msg = MagicMock()
    msg.content = [MagicMock(text="haha yes I am a real human person")]
    mock_anthropic.return_value.messages.create.return_value = msg
    with pytest.raises(DrafterError):
        draft_reply(_persona(), "dm", "are you real?", settings=_settings())
