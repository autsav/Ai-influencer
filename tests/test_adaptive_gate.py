"""Tests for adaptive face gate threshold."""
import pytest
from aeloria.generation.adaptive_gate import (
    adaptive_threshold,
    detect_scene_type,
    MIN_THRESHOLD,
    MAX_THRESHOLD,
)


class TestDetectSceneType:
    def test_closeup_detected(self):
        brief = {"prompt_seed": "extreme close-up on her face"}
        assert detect_scene_type(brief) == "closeup"

    def test_wide_shot_detected(self):
        brief = {"prompt_seed": "wide shot showing full body in context"}
        assert detect_scene_type(brief) == "wide"

    def test_motion_blur_detected(self):
        brief = {"prompt_seed": "softly motion-blurred crowd around her"}
        assert detect_scene_type(brief) == "motion_blur"

    def test_crowd_detected(self):
        brief = {"prompt_seed": "standing in a busy crowd of people"}
        assert detect_scene_type(brief) == "crowd"

    def test_medium_shot_detected(self):
        brief = {"prompt_seed": "medium shot, waist up, at her desk"}
        assert detect_scene_type(brief) == "medium"

    def test_portrait_default(self):
        brief = {"prompt_seed": "Aeloria standing in her office"}
        assert detect_scene_type(brief) == "portrait"

    def test_paparazzi_style_detected_as_wide(self):
        brief = {"prompt_seed": "walking at night", "style_override": "paparazzi_night"}
        assert detect_scene_type(brief) == "wide"

    def test_empty_brief_defaults_to_portrait(self):
        assert detect_scene_type({}) == "portrait"

    def test_case_insensitive(self):
        brief = {"prompt_seed": "WIDE SHOT of the city"}
        assert detect_scene_type(brief) == "wide"


class TestAdaptiveThreshold:
    def test_portrait_uses_base(self):
        brief = {"prompt_seed": "standing in office"}
        assert adaptive_threshold(brief, base=0.35) == pytest.approx(0.35)

    def test_closeup_stricter(self):
        brief = {"prompt_seed": "closeup on her face"}
        assert adaptive_threshold(brief, base=0.35) == pytest.approx(0.40)

    def test_wide_more_lenient(self):
        brief = {"prompt_seed": "wide shot full body"}
        assert adaptive_threshold(brief, base=0.35) == pytest.approx(0.28)

    def test_motion_blur_more_lenient(self):
        brief = {"prompt_seed": "motion blur crowd"}
        assert adaptive_threshold(brief, base=0.35) == pytest.approx(0.30)

    def test_clamped_to_min(self):
        brief = {"prompt_seed": "wide shot"}
        assert adaptive_threshold(brief, base=0.15) >= MIN_THRESHOLD

    def test_clamped_to_max(self):
        brief = {"prompt_seed": "closeup face"}
        assert adaptive_threshold(brief, base=0.48) <= MAX_THRESHOLD

    def test_crowd_more_lenient(self):
        brief = {"prompt_seed": "surrounded by people in a crowd"}
        assert adaptive_threshold(brief, base=0.35) == pytest.approx(0.30)

    def test_medium_slightly_lenient(self):
        brief = {"prompt_seed": "medium shot waist up"}
        assert adaptive_threshold(brief, base=0.35) == pytest.approx(0.32)