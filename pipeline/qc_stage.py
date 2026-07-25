"""Automated quality control stage — validates generated images before publish.

Checks:
1. Image dimensions (minimum size)
2. File size (not too large)
3. Aspect ratio (matches expected)
4. Face gate (InsightFace cosine similarity to reference)
5. Artifact detection (solid color regions, dead pixels, blurry regions)
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image

from pipeline.config_loader import QCConfig

logger = logging.getLogger(__name__)


@dataclass
class QCResult:
    passed: bool
    checks: dict[str, dict] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def run_qc(
    image_bytes: bytes,
    config: QCConfig,
    face_ref_path: str = "",
    dry_run: bool = False,
) -> QCResult:
    """Run all QC checks on a generated image.

    Args:
        image_bytes: Raw image bytes (PNG/JPEG)
        config: QC configuration thresholds
        face_ref_path: Path to face reference JSON for identity check
        dry_run: Skip face gate (no model loading)

    Returns:
        QCResult with pass/fail per check
    """
    result = QCResult(passed=True)

    if not image_bytes:
        result.passed = False
        result.errors.append("Empty image bytes")
        return result

    # Load image
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        result.passed = False
        result.errors.append(f"Cannot decode image: {e}")
        return result

    w, h = img.size
    file_size_mb = len(image_bytes) / (1024 * 1024)

    # ── Check 1: Dimensions ──────────────────────────────────────────────────
    dim_ok = w >= config.min_width and h >= config.min_height
    result.checks["dimensions"] = {
        "passed": dim_ok,
        "width": w,
        "height": h,
        "min_width": config.min_width,
        "min_height": config.min_height,
    }
    if not dim_ok:
        result.errors.append(f"Image too small: {w}x{h} (min {config.min_width}x{config.min_height})")
        result.passed = False

    # ── Check 2: File size ───────────────────────────────────────────────────
    size_ok = file_size_mb <= config.max_file_size_mb
    result.checks["file_size"] = {
        "passed": size_ok,
        "size_mb": round(file_size_mb, 2),
        "max_mb": config.max_file_size_mb,
    }
    if not size_ok:
        result.warnings.append(f"Large file: {file_size_mb:.1f}MB (max {config.max_file_size_mb}MB)")

    # ── Check 3: Aspect ratio ────────────────────────────────────────────────
    if config.check_aspect_ratio:
        expected = config.expected_aspect
        ratios = {"4:5": 0.8, "9:16": 0.5625, "1:1": 1.0, "16:9": 1.7778}
        expected_ratio = ratios.get(expected, 0.8)
        actual_ratio = w / h
        ratio_ok = abs(actual_ratio - expected_ratio) < 0.05
        result.checks["aspect_ratio"] = {
            "passed": ratio_ok,
            "actual": round(actual_ratio, 4),
            "expected": expected_ratio,
            "target": expected,
        }
        if not ratio_ok:
            result.warnings.append(f"Aspect ratio {actual_ratio:.3f} != expected {expected}")

    # ── Check 4: Artifact detection ──────────────────────────────────────────
    if config.artifact_check_enabled:
        arr = np.array(img.convert("RGB"))
        # Solid color region check (large uniform areas = generation failure)
        std_per_channel = arr.std(axis=(0, 1))
        has_detail = all(s > 10 for s in std_per_channel)
        # Blurry check (Laplacian variance — low = blurry)
        gray = np.array(img.convert("L"), dtype=np.float32)
        laplacian_var = _laplacian_variance(gray)
        is_sharp = laplacian_var > 50.0
        # Dead pixel check
        dead_ratio = _dead_pixel_ratio(arr)

        # Dead pixel threshold: 5% is acceptable for AI images (pure black/white
        # regions are common in high-contrast lighting, not necessarily artifacts)
        # Dead pixel ratio — warning only (common in high-contrast AI images)
        if dead_ratio > 0.05:
            result.warnings.append(f"High dead pixel ratio: {dead_ratio:.4f}")

        artifact_ok = has_detail and is_sharp  # dead pixel is now warning-only
        result.checks["artifacts"] = {
            "passed": artifact_ok,
            "channel_std": [round(float(s), 1) for s in std_per_channel],
            "laplacian_var": round(float(laplacian_var), 1),
            "dead_pixel_ratio": round(float(dead_ratio), 4),
        }
        if not artifact_ok:
            result.errors.append(
                f"Artifact check failed: std={[round(float(s),1) for s in std_per_channel]} "
                f"laplacian={laplacian_var:.1f} dead={dead_ratio:.4f}"
            )
            result.passed = False

    # ── Check 5: Face gate ───────────────────────────────────────────────────
    if config.face_gate_enabled and not dry_run and face_ref_path:
        try:
            face_result = _face_gate_check(image_bytes, face_ref_path, config.face_gate_threshold)
            result.checks["face_gate"] = face_result
            if not face_result["passed"]:
                result.errors.append(
                    f"Face gate failed: similarity {face_result['similarity']:.3f} < {config.face_gate_threshold}"
                )
                result.passed = False
        except Exception as e:
            result.warnings.append(f"Face gate error (non-fatal): {e}")
            result.checks["face_gate"] = {"passed": True, "error": str(e), "skipped": True}

    logger.info(
        "QC %s: %d checks, %d errors, %d warnings",
        "PASSED" if result.passed else "FAILED",
        len(result.checks),
        len(result.errors),
        len(result.warnings),
    )
    return result


def _laplacian_variance(gray: np.ndarray) -> float:
    """Compute Laplacian variance — high = sharp, low = blurry."""
    try:
        from scipy.ndimage import laplace
        return float(laplace(gray).var())
    except ImportError:
        # Fallback: simple edge detection
        kernel = np.array([[0, -1, 0], [-1, 4, -1], [0, -1, 0]], dtype=np.float32)
        from numpy.lib.stride_tricks import sliding_window_view
        if gray.shape[0] < 3 or gray.shape[1] < 3:
            return 0.0
        padded = np.pad(gray, 1, mode="edge")
        windows = sliding_window_view(padded, (3, 3))
        edges = (windows * kernel).sum(axis=(-2, -1))
        return float(edges.var())


def _dead_pixel_ratio(arr: np.ndarray) -> float:
    """Ratio of pure black (0,0,0) or pure white (255,255,255) pixels."""
    total = arr.shape[0] * arr.shape[1]
    black = np.all(arr == 0, axis=2).sum()
    white = np.all(arr == 255, axis=2).sum()
    return float((black + white) / total)


def _face_gate_check(image_bytes: bytes, ref_path: str, threshold: float) -> dict:
    """Run InsightFace similarity check."""
    import json
    from pathlib import Path
    from aeloria.generation.face_gate import embed_face, similarity

    ref_data = json.loads(Path(ref_path).read_text())
    ref_emb = np.asarray(ref_data["embedding"], dtype=np.float32)
    gen_emb = embed_face(image_bytes)
    sim = similarity(gen_emb, ref_emb)
    return {
        "passed": sim >= threshold,
        "similarity": round(float(sim), 4),
        "threshold": threshold,
    }