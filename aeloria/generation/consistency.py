"""Character Consistency Engine — two-pass identity preservation pipeline.

Pass 1: Base generation via FLUX.1 + LoRA + PuLID face identity embedding
Pass 2: Face detailer refinement — detect face crop, low-denoise inpaint

Architecture:
    reference_face → embed_identity() → identity_vector
    brief → build_prompt() → Pass 1 (fal.ai FLUX + LoRA + PuLID)
    Pass 1 output → detect_face_crop() → Pass 2 (fal.ai inpaint face region)
    Pass 2 output → verify_identity() → final image

All identity weights clamped to [0.6, 1.1].
Face detailer denoise clamped to [0.15, 0.40].
"""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ── Weight clamping constants ────────────────────────────────────────────────
MIN_IDENTITY_WEIGHT = 0.6
MAX_IDENTITY_WEIGHT = 1.1
MIN_DENOISE = 0.15
MAX_DENOISE = 0.40

# Default PuLID weight — higher = stronger face match, but risks artifacts
DEFAULT_PULID_WEIGHT = 0.85

# Default face detailer denoise — low enough to fix artifacts without identity drift
DEFAULT_FACE_DENOISE = 0.28


def clamp_identity_weight(weight: float) -> float:
    """Clamp PuLID/InstantID/IP-Adapter weight to safe range [0.6, 1.1]."""
    clamped = max(MIN_IDENTITY_WEIGHT, min(MAX_IDENTITY_WEIGHT, weight))
    if clamped != weight:
        log.warning("Identity weight clamped from %.2f to %.2f", weight, clamped)
    return clamped


def clamp_denoise(denoise: float) -> float:
    """Clamp face detailer denoise to safe range [0.15, 0.40]."""
    clamped = max(MIN_DENOISE, min(MAX_DENOISE, denoise))
    if clamped != denoise:
        log.warning("Face denoise clamped from %.2f to %.2f", denoise, clamped)
    return clamped


@dataclass
class IdentityEmbedding:
    """Face identity vector extracted from a reference image."""
    embedding: np.ndarray          # InsightFace 512-d normed embedding
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2) of reference face
    source: str                    # Description of source (e.g. "face_ref.json")


@dataclass
class FaceCrop:
    """Detected face region in a generated image."""
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixels
    confidence: float
    image_width: int
    image_height: int

    @property
    def face_size(self) -> int:
        return max(self.bbox[2] - self.bbox[0], self.bbox[3] - self.bbox[1])

    @property
    def needs_detail_pass(self) -> bool:
        """Faces smaller than 256px in a wide shot benefit from detail refinement."""
        return self.face_size < 256


@dataclass
class ConsistencyResult:
    """Result of the two-pass consistency pipeline."""
    image_bytes: bytes
    identity_score: float          # cosine similarity to reference
    passes_gate: bool
    pass1_score: float             # identity score after Pass 1
    pass2_score: float             # identity score after Pass 2 (same as pass1 if no Pass 2)
    detail_pass_applied: bool
    cost_usd: float
    face_crop: Optional[FaceCrop] = None


def extract_identity(reference_bytes: bytes) -> IdentityEmbedding:
    """
    Extract face identity embedding from a reference image using InsightFace.

    This embedding is passed to PuLID/InstantID at runtime for zero-shot identity preservation.
    """
    from aeloria.generation.face_gate import embed_face

    import cv2

    # Get the embedding
    embedding = embed_face(reference_bytes)

    # Get bounding box of the largest face
    arr = np.frombuffer(reference_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    from aeloria.generation.face_gate import _analyzer
    faces = _analyzer().get(img)
    if not faces:
        raise ValueError("No face found in reference image")
    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    bbox = tuple(faces[0].bbox)

    log.info("Identity extracted: embedding shape=%s, bbox=%s", embedding.shape, bbox)
    return IdentityEmbedding(embedding=embedding, bbox=bbox, source="reference_image")


def detect_face_crop(image_bytes: bytes) -> Optional[FaceCrop]:
    """
    Detect the largest face in a generated image and return its crop region.
    Uses InsightFace (already installed for face_gate).
    """
    import cv2

    from aeloria.generation.face_gate import _analyzer

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        log.warning("Cannot decode image for face detection")
        return None

    h, w = img.shape[:2]
    faces = _analyzer().get(img)
    if not faces:
        log.info("No face detected in generated image — skipping detail pass")
        return None

    # Largest face
    faces.sort(key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)
    f = faces[0]
    x1, y1, x2, y2 = int(f.bbox[0]), int(f.bbox[1]), int(f.bbox[2]), int(f.bbox[3])

    # Expand crop by 20% padding for context
    pad = int(max(x2 - x1, y2 - y1) * 0.2)
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)

    crop = FaceCrop(
        bbox=(x1, y1, x2, y2),
        confidence=float(f.det_score),
        image_width=w,
        image_height=h,
    )
    log.info("Face detected: %dx%d at %s, confidence=%.3f, needs_detail=%s",
             crop.face_size, crop.face_size, crop.bbox, crop.confidence, crop.needs_detail_pass)
    return crop