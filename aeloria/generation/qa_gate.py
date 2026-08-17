"""
Critic / QA Gate — multi-agent pipeline quality enforcement.

Adapted from engineering-multi-agent-systems-architect.md (evaluator/observability role).

Enforces:
  - Image quality (warmth R/G 1.08-1.15, edge energy ≤0.020)
  - Caption quality (length, hashtag count, CTA presence)
  - Returns pass/fail with specific failure_reasons

Pixels measured with PIL only (no external deps beyond stdlib + numpy/pillow already in venv).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from PIL import Image, ImageFilter


@dataclass
class ImageMetrics:
    warmth_RG: float
    warmth_RB: float
    edge_energy: float
    luminance_mean: float
    all_pass: bool


@dataclass
class CaptionMetrics:
    length_words: int
    hashtag_count: int
    cta_present: bool
    hook_in_first_2_lines: bool
    all_pass: bool


@dataclass
class QAResult:
    passed: bool
    image_metrics: ImageMetrics
    caption_metrics: CaptionMetrics
    failure_reasons: list[str] = field(default_factory=list)
    confidence: float = 0.85

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "image_metrics": self.image_metrics.__dict__,
            "caption_metrics": self.caption_metrics.__dict__,
            "failure_reasons": self.failure_reasons,
            "confidence": self.confidence,
        }


# Default thresholds (calibrated against reference Whisk_*.png images)
DEFAULT_IMAGE_THRESHOLDS = {
    "warmth_RG_min": 1.08,
    "warmth_RG_max": 1.15,
    "warmth_RB_min": 1.16,
    "warmth_RB_max": 1.25,
    "edge_energy_max": 0.020,
    "luminance_min": 0.20,
    "luminance_max": 0.45,
}

DEFAULT_CAPTION_THRESHOLDS = {
    "feed_min_words": 50,
    "feed_max_words": 300,
    "reels_min_words": 20,
    "reels_max_words": 80,
    "max_hashtags": 30,
    "cta_keywords": ["save", "follow", "comment", "share", "tag", "dm", "link in bio"],
}


class QAGate:
    """Quality gate — fail fast on metrics outside thresholds."""

    def __init__(
        self,
        image_thresholds: dict[str, float] | None = None,
        caption_thresholds: dict[str, Any] | None = None,
    ):
        self.image_t = image_thresholds or DEFAULT_IMAGE_THRESHOLDS
        self.caption_t = {**DEFAULT_CAPTION_THRESHOLDS, **(caption_thresholds or {})}

    # ── Image metrics ────────────────────────────────────────────────────────
    def evaluate_image(self, image_bytes: bytes) -> ImageMetrics:
        """Compute warmth, edge energy, luminance on center-cropped image."""
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        # Center crop to 60% — exclude UI overlays, focus on subject
        w, h = img.size
        crop_w, crop_h = int(w * 0.6), int(h * 0.6)
        left = (w - crop_w) // 2
        top = (h - crop_h) // 2
        cropped = img.crop((left, top, left + crop_w, top + crop_h))

        arr = np.array(cropped).astype(np.float32)
        R = arr[..., 0]
        G = arr[..., 1]
        B = arr[..., 2]

        warmth_RG = float(R.mean() / max(G.mean(), 1.0))
        warmth_RB = float(R.mean() / max(B.mean(), 1.0))

        # Luminance (Rec. 709)
        luminance = 0.2126 * R + 0.7152 * G + 0.0722 * B
        luminance_mean = float(luminance.mean() / 255.0)

        # Edge energy via Sobel-like (PIL FIND_EDGES)
        edges = cropped.convert("L").filter(ImageFilter.FIND_EDGES)
        edge_arr = np.array(edges).astype(np.float32)
        edge_energy = float(edge_arr.mean() / 255.0)

        # Pass/fail checks
        all_pass = (
            self.image_t["warmth_RG_min"] <= warmth_RG <= self.image_t["warmth_RG_max"]
            and self.image_t["warmth_RB_min"] <= warmth_RB <= self.image_t["warmth_RB_max"]
            and edge_energy <= self.image_t["edge_energy_max"]
            and self.image_t["luminance_min"] <= luminance_mean <= self.image_t["luminance_max"]
        )

        return ImageMetrics(
            warmth_RG=round(warmth_RG, 3),
            warmth_RB=round(warmth_RB, 3),
            edge_energy=round(edge_energy, 4),
            luminance_mean=round(luminance_mean, 3),
            all_pass=all_pass,
        )

    def image_failure_reasons(self, metrics: ImageMetrics) -> list[str]:
        reasons = []
        if metrics.warmth_RG < self.image_t["warmth_RG_min"]:
            reasons.append("warmth_RG_too_low")
        elif metrics.warmth_RG > self.image_t["warmth_RG_max"]:
            reasons.append("warmth_RG_too_high")
        if metrics.warmth_RB < self.image_t["warmth_RB_min"]:
            reasons.append("warmth_RB_too_low")
        elif metrics.warmth_RB > self.image_t["warmth_RB_max"]:
            reasons.append("warmth_RB_too_high")
        if metrics.edge_energy > self.image_t["edge_energy_max"]:
            reasons.append("edge_energy_too_high")
        if metrics.luminance_mean < self.image_t["luminance_min"]:
            reasons.append("luminance_too_dark")
        elif metrics.luminance_mean > self.image_t["luminance_max"]:
            reasons.append("luminance_too_bright")
        return reasons

    # ── Caption metrics ──────────────────────────────────────────────────────
    def evaluate_caption(self, caption: str, format_type: str = "feed") -> CaptionMetrics:
        words = caption.split()
        length = len(words)

        # Hashtag count
        hashtag_count = sum(1 for w in words if w.startswith("#"))

        # CTA presence
        caption_lower = caption.lower()
        cta_present = any(kw in caption_lower for kw in self.caption_t["cta_keywords"])

        # Hook in first 2 lines
        first_2_lines = "\n".join(caption.split("\n")[:2])
        hook_in_first_2 = bool(first_2_lines.strip()) and len(first_2_lines.split()) >= 3

        # Length check by format
        if format_type == "reel":
            length_ok = self.caption_t["reels_min_words"] <= length <= self.caption_t["reels_max_words"]
        else:
            length_ok = self.caption_t["feed_min_words"] <= length <= self.caption_t["feed_max_words"]

        hashtag_ok = hashtag_count <= self.caption_t["max_hashtags"]

        all_pass = length_ok and hashtag_ok and cta_present and hook_in_first_2

        return CaptionMetrics(
            length_words=length,
            hashtag_count=hashtag_count,
            cta_present=cta_present,
            hook_in_first_2_lines=hook_in_first_2,
            all_pass=all_pass,
        )

    # ── Combined ─────────────────────────────────────────────────────────────
    def evaluate(
        self,
        image_bytes: bytes | None = None,
        caption: str | None = None,
        caption_format: str = "feed",
    ) -> QAResult:
        """Combined image + caption evaluation."""
        image_metrics = self.evaluate_image(image_bytes) if image_bytes else ImageMetrics(
            warmth_RG=0, warmth_RB=0, edge_energy=0, luminance_mean=0, all_pass=True
        )
        caption_metrics = self.evaluate_caption(caption, caption_format) if caption else CaptionMetrics(
            length_words=0, hashtag_count=0, cta_present=False, hook_in_first_2_lines=False, all_pass=True
        )

        failure_reasons = self.image_failure_reasons(image_metrics) if not image_metrics.all_pass else []
        if not caption_metrics.all_pass:
            if caption_metrics.length_words < 50:
                failure_reasons.append("caption_too_short")
            if not caption_metrics.cta_present:
                failure_reasons.append("caption_missing_cta")
            if not caption_metrics.hook_in_first_2_lines:
                failure_reasons.append("caption_no_hook_in_first_2_lines")

        return QAResult(
            passed=image_metrics.all_pass and caption_metrics.all_pass,
            image_metrics=image_metrics,
            caption_metrics=caption_metrics,
            failure_reasons=failure_reasons,
            confidence=0.87,
        )
