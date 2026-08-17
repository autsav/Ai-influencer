"""Smoke tests for qa_gate.

Verifies:
- import
- QAGate instantiation with default thresholds
- evaluate_image accepts a synthetic image (PIL.Image or path)
"""

import io
from aeloria.generation.qa_gate import (
    QAGate,
    QAResult,
    DEFAULT_IMAGE_THRESHOLDS,
)


def _make_test_image_bytes() -> bytes:
    """Tiny 8x8 PNG so QA gate has something to score."""
    try:
        from PIL import Image
    except ImportError:
        return b""
    img = Image.new("RGB", (8, 8), color=(120, 90, 60))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_qa_gate_imports():
    assert QAGate is not None
    assert QAResult is not None
    assert isinstance(DEFAULT_IMAGE_THRESHOLDS, dict)


def test_qa_gate_instantiates_with_defaults():
    gate = QAGate()
    assert gate is not None
    assert gate.image_t is not None
    assert gate.caption_t is not None


def test_qa_gate_evaluates_image():
    from PIL import Image
    import io
    gate = QAGate()
    img = Image.new("RGB", (64, 64), color=(80, 100, 120))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    image_bytes = buf.getvalue()
    result = gate.evaluate_image(image_bytes)
    assert result is not None
    assert hasattr(result, "all_pass") or hasattr(result, "passed") or hasattr(result, "score")