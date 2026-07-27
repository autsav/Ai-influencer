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
    return s


def test_claims_human_detects_assertions():
    assert claims_human("Yes, I'm a real person!")
    assert claims_human("i am human, not a bot")
    assert claims_human("Actually I am a real girl")
    assert claims_human("I'm a living, breathing person")
    assert claims_human("I promise I'm not artificial")
    assert not claims_human("I'm so glad this resonated 🌲")


@patch("aeloria.engagement.drafter.llm_generate")
def test_draft_reply_returns_text(mock_llm):
    mock_llm.return_value = "so glad you felt that 🌲"
    out = draft_reply(_persona(), "reply", "love this so calm", settings=_settings())
    assert out == "so glad you felt that 🌲"
    prompt = mock_llm.call_args.args[0]
    assert "never" in prompt.lower()


@patch("aeloria.engagement.drafter.llm_generate")
def test_draft_reply_blocks_human_claim(mock_llm):
    mock_llm.return_value = "haha yes I am a real human person"
    with pytest.raises(DrafterError):
        draft_reply(_persona(), "dm", "are you real?", settings=_settings())