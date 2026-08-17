"""Smoke tests for caption_agent.

Verifies:
- import
- CaptionAgent instantiation
- one generate() call returns a CaptionResult-like object
"""

from aeloria.generation.caption_agent import (
    CaptionAgent,
    CaptionResult,
    HOOK_TEMPLATES_BY_PILLAR,
)


def test_caption_agent_imports():
    assert CaptionAgent is not None
    assert CaptionResult is not None


def test_caption_agent_instantiates():
    agent = CaptionAgent()
    assert agent is not None


def test_caption_agent_create_caption_returns_result():
    agent = CaptionAgent()
    pillar = list(HOOK_TEMPLATES_BY_PILLAR.keys())[0]
    result = agent.create_caption(content_pillar=pillar, topic="AI workflow test")
    assert result is not None
    # CaptionResult exposes feed_caption (Pydantic) with hook/body fields
    assert hasattr(result, "feed_caption") or hasattr(result, "caption") or hasattr(result, "text")
    if hasattr(result, "feed_caption"):
        assert result.feed_caption.hook  # non-empty hook
        assert result.feed_caption.body  # non-empty body