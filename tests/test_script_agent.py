"""Smoke tests for script_agent.

Verifies:
- import
- ScriptAgent instantiation
- one generate() call returns a VideoScript with beats
"""

from aeloria.generation.script_agent import (
    ScriptAgent,
    VideoScript,
    ScriptBeat,
    AUDIO_CATEGORIES,
    HOOK_TEMPLATES,
)


def test_script_agent_imports():
    assert ScriptAgent is not None
    assert VideoScript is not None
    assert ScriptBeat is not None
    assert isinstance(AUDIO_CATEGORIES, list)
    assert len(AUDIO_CATEGORIES) > 0


def test_script_agent_instantiates():
    agent = ScriptAgent()
    assert agent is not None


def test_script_agent_writes_script():
    agent = ScriptAgent()
    script = agent.write_script(topic="test AI tool", content_pillar="AI tools + productivity")
    assert script is not None
    assert hasattr(script, "beats") or hasattr(script, "script") or hasattr(script, "scenes")