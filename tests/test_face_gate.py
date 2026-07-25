import json

import numpy as np
import pytest
from unittest.mock import patch

from aeloria.generation.face_gate import (
    FaceGateError,
    load_reference,
    passes_gate,
    similarity,
)


def test_similarity_identical_is_one():
    v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    assert similarity(v, v) == pytest.approx(1.0)


def test_similarity_orthogonal_is_zero():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    assert similarity(a, b) == pytest.approx(0.0)


def test_load_reference(tmp_path):
    p = tmp_path / "ref.json"
    p.write_text(json.dumps({"embedding": [0.6, 0.8], "count": 20}))
    ref = load_reference(str(p))
    assert ref.dtype == np.float32
    assert ref.tolist() == pytest.approx([0.6, 0.8])


@patch("aeloria.generation.face_gate.embed_face")
def test_passes_gate_above_threshold(mock_embed):
    ref = np.array([1.0, 0.0], dtype=np.float32)
    mock_embed.return_value = np.array([0.9, 0.1], dtype=np.float32)
    sim, ok = passes_gate(b"img", ref, threshold=0.35)
    assert ok and sim > 0.9


@patch("aeloria.generation.face_gate.embed_face")
def test_passes_gate_below_threshold(mock_embed):
    ref = np.array([1.0, 0.0], dtype=np.float32)
    mock_embed.return_value = np.array([0.0, 1.0], dtype=np.float32)
    sim, ok = passes_gate(b"img", ref, threshold=0.35)
    assert not ok and sim == pytest.approx(0.0)
