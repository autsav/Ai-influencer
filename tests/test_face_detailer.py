"""Tests for the face detailer (Pass 2) module."""
import pytest
from unittest.mock import MagicMock, patch

from aeloria.generation.consistency import FaceCrop
from aeloria.generation.face_detailer import (
    maybe_refine_face,
    refine_face,
    FACE_DETAIL_PROMPT,
    DEFAULT_FACE_DENOISE,
    GenerationError,
)


class TestFaceDetailPrompt:
    def test_prompt_mentions_facial_features(self):
        assert "detailed face" in FACE_DETAIL_PROMPT
        assert "eyes" in FACE_DETAIL_PROMPT
        assert "skin texture" in FACE_DETAIL_PROMPT


class TestMaybeRefineFace:
    def test_disabled_returns_original(self):
        """When face_detailer_enabled=False, return original image unchanged."""
        settings = MagicMock()
        settings.face_detailer_enabled = False

        result_bytes, applied = maybe_refine_face(b"original", settings)
        assert result_bytes == b"original"
        assert applied is False

    def test_face_large_enough_skips_detail(self):
        """When face > 256px, detail pass is skipped."""
        settings = MagicMock()
        settings.face_detailer_enabled = True

        large_face = FaceCrop(bbox=(0, 0, 400, 400), confidence=0.95, image_width=896, image_height=1152)
        result_bytes, applied = maybe_refine_face(b"original", settings, face_crop=large_face)
        assert result_bytes == b"original"
        assert applied is False

    def test_face_small_triggers_detail(self):
        """When face < 256px, detail pass is attempted."""
        settings = MagicMock()
        settings.face_detailer_enabled = True

        small_face = FaceCrop(bbox=(100, 100, 200, 200), confidence=0.9, image_width=896, image_height=1152)

        with patch("aeloria.generation.face_detailer.refine_face") as mock_refine:
            mock_refine.return_value = b"refined"
            result_bytes, applied = maybe_refine_face(b"original", settings, face_crop=small_face)
            assert result_bytes == b"refined"
            assert applied is True

    def test_refine_failure_returns_original(self):
        """If refine_face raises, return original image."""
        settings = MagicMock()
        settings.face_detailer_enabled = True

        small_face = FaceCrop(bbox=(100, 100, 200, 200), confidence=0.9, image_width=896, image_height=1152)

        with patch("aeloria.generation.face_detailer.refine_face", side_effect=GenerationError("fal down")):
            result_bytes, applied = maybe_refine_face(b"original", settings, face_crop=small_face)
            assert result_bytes == b"original"
            assert applied is False