"""Smoke tests for image_prompt_engineer.

Verifies:
- import
- ImagePromptEngineer instantiation
- one build() call returns an ImagePrompt-like object
"""

from aeloria.generation.image_prompt_engineer import (
    ImagePrompt,
    ImagePromptEngineer,
)


def test_image_prompt_engineer_imports():
    assert ImagePromptEngineer is not None
    assert ImagePrompt is not None


def test_image_prompt_engineer_instantiates():
    eng = ImagePromptEngineer()
    assert eng is not None


def test_image_prompt_engineer_build_prompt_returns_prompt():
    eng = ImagePromptEngineer()
    prompt = eng.build_prompt(scene="coffee shop working on laptop")
    assert prompt is not None
    assert hasattr(prompt, "prompt") or hasattr(prompt, "text")