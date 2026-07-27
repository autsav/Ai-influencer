"""Tests for the character consistency engine — clamping, face detection, pipeline."""
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from aeloria.generation.consistency import (
    clamp_identity_weight,
    clamp_denoise,
    MIN_IDENTITY_WEIGHT,
    MAX_IDENTITY_WEIGHT,
    MIN_DENOISE,
    MAX_DENOISE,
    FaceCrop,
    ConsistencyResult,
)


class TestClampIdentityWeight:
    def test_clamps_below_min(self):
        assert clamp_identity_weight(0.3) == MIN_IDENTITY_WEIGHT

    def test_clamps_above_max(self):
        assert clamp_identity_weight(1.5) == MAX_IDENTITY_WEIGHT

    def test_passes_valid_weight(self):
        assert clamp_identity_weight(0.85) == 0.85

    def test_clamps_exact_min(self):
        assert clamp_identity_weight(0.6) == 0.6

    def test_clamps_exact_max(self):
        assert clamp_identity_weight(1.1) == 1.1


class TestClampDenoise:
    def test_clamps_below_min(self):
        assert clamp_denoise(0.05) == MIN_DENOISE

    def test_clamps_above_max(self):
        assert clamp_denoise(0.6) == MAX_DENOISE

    def test_passes_valid_denoise(self):
        assert clamp_denoise(0.28) == 0.28

    def test_clamps_exact_min(self):
        assert clamp_denoise(0.15) == 0.15

    def test_clamps_exact_max(self):
        assert clamp_denoise(0.40) == 0.40


class TestFaceCrop:
    def test_face_size(self):
        crop = FaceCrop(bbox=(100, 100, 356, 356), confidence=0.95, image_width=896, image_height=1152)
        assert crop.face_size == 256

    def test_needs_detail_pass_when_small(self):
        crop = FaceCrop(bbox=(100, 100, 200, 200), confidence=0.9, image_width=896, image_height=1152)
        assert crop.face_size == 100
        assert crop.needs_detail_pass is True

    def test_does_not_need_detail_pass_when_large(self):
        crop = FaceCrop(bbox=(100, 100, 500, 500), confidence=0.9, image_width=896, image_height=1152)
        assert crop.face_size == 400
        assert crop.needs_detail_pass is False

    def test_needs_detail_pass_at_boundary(self):
        crop = FaceCrop(bbox=(0, 0, 256, 256), confidence=0.9, image_width=896, image_height=1152)
        assert crop.face_size == 256
        assert crop.needs_detail_pass is False


class TestConsistencyResult:
    def test_dataclass_fields(self):
        r = ConsistencyResult(
            image_bytes=b"fake",
            identity_score=0.65,
            passes_gate=True,
            pass1_score=0.60,
            pass2_score=0.65,
            detail_pass_applied=True,
            cost_usd=0.10,
        )
        assert r.identity_score == 0.65
        assert r.passes_gate is True
        assert r.detail_pass_applied is True
        assert r.cost_usd == 0.10