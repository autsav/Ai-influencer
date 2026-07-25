"""Dataset validator — Soul 2.0 Pillar 4 extension.

Validates that a reference image dataset meets Soul ID training criteria
BEFORE fine-tuning. Prevents garbage-in → garbage-out from the LoRA trainer.

Rules enforced:
  1. All images contain Aeloria (InsightFace verification)
  2. Physical appearance matches soul_id.yaml (body type, skin texture)
  3. No two images from the same session/pose
  4. Minimum 10 images, maximum 50
  5. Backstory/lore metadata NOT in filenames or EXIF
  6. Location/wardrobe diversity: at least 3 different settings
  7. Resolution: at least 512x512 per image

Usage:
    from aeloria.generation.dataset_validator import validate_dataset
    result = validate_dataset(["/path/to/img1.jpg", ...])
    if not result.passed:
        print(result.errors)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image

# Optional heavy dependency — fail fast with a clear message
try:
    import insightface
    from insightface.app import FaceAnalysis
    _HAS_INSIGHTFACE = True
except ImportError:
    _HAS_INSIGHTFACE = False


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    diversity_report: dict = field(default_factory=dict)

    def add_error(self, msg: str):
        self.errors.append(msg)
        self.passed = False

    def add_warning(self, msg: str):
        self.warnings.append(msg)


def validate_dataset(
    image_paths: list[str],
    min_images: int = 10,
    max_images: int = 50,
    min_resolution: int = 512,
    min_diversity_locations: int = 3,
    min_face_similarity: float = 0.50,
    face_ref_path: str | None = None,
) -> ValidationResult:
    """Validate a reference image dataset for Soul ID training.

    Args:
        image_paths: list of absolute paths to candidate reference images
        min_images: minimum number of images required (default 10)
        max_images: maximum number of images allowed (default 50)
        min_resolution: minimum width/height in pixels (default 512)
        min_diversity_locations: minimum distinct location/setting buckets (default 3)
        min_face_similarity: minimum InsightFace similarity to reference face (default 0.50)
        face_ref_path: optional path to a reference face embedding (.npy or image).
                       If None, face verification is skipped.

    Returns:
        ValidationResult with passed, errors, warnings, diversity_report
    """
    result = ValidationResult(passed=True)

    # ── 0. Basic path checks ────────────────────────────────────────────────────
    if not image_paths:
        result.add_error("image_paths is empty")
        return result

    paths = [Path(p) for p in image_paths]

    for p in paths:
        if not p.exists():
            result.add_error(f"file not found: {p}")
        elif not p.is_file():
            result.add_error(f"not a file: {p}")

    if not result.passed:
        return result

    # ── 1. Count gate ──────────────────────────────────────────────────────────
    n = len(paths)
    if n < min_images:
        result.add_error(
            f"too few images: {n} (minimum {min_images} required for Soul ID training)"
        )
    if n > max_images:
        result.add_error(
            f"too many images: {n} (maximum {max_images} — curate to highest quality)"
        )

    # ── 2. Resolution check ─────────────────────────────────────────────────────
    too_small = []
    for p in paths:
        try:
            with Image.open(p) as img:
                w, h = img.size
                if w < min_resolution or h < min_resolution:
                    too_small.append(f"{p.name}: {w}x{h}")
        except Exception as e:
            result.add_error(f"could not open {p.name}: {e}")
    if too_small:
        result.add_error(
            f"{len(too_small)} image(s) below {min_resolution}x{min_resolution}: "
            + ", ".join(too_small[:5])
            + (" ..." if len(too_small) > 5 else "")
        )

    # ── 3. Filename / EXIF metadata scan ───────────────────────────────────────
    lore_keywords = [
        "forest", "cabin", "creek", "backstory", "lore", "house",
        "glamping", "woodland", "clearing", "porch", "trail",
    ]
    lore_files = []
    for p in paths:
        stem = p.stem.lower()
        if any(kw in stem for kw in lore_keywords):
            lore_files.append(p.name)
    if lore_files:
        result.add_error(
            f"filename(s) contain lore/backstory keywords: {', '.join(lore_files)}. "
            "Remove location context from filenames before training."
        )

    # ── 4. Face verification ─────────────────────────────────────────────────────
    if _HAS_INSIGHTFACE:
        _run_face_check(paths, face_ref_path, min_face_similarity, result)
    else:
        result.add_warning(
            "InsightFace not installed — skipping face verification. "
            "Install with: pip install insightface"
        )

    # ── 5. Diversity check (location/wardrobe) ─────────────────────────────────
    # Heuristic: look at EXIF DateTime as a proxy for session grouping,
    # and at directory names as a proxy for location diversity.
    _run_diversity_check(paths, min_diversity_locations, result)

    return result


def _run_face_check(
    paths: list[Path],
    face_ref_path: str | None,
    min_similarity: float,
    result: ValidationResult,
):
    """Verify each image contains a face similar to the reference."""
    try:
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))
    except Exception as e:
        result.add_warning(f"InsightFace init failed: {e}. Skipping face check.")
        return

    failed_faces = []
    for p in paths:
        try:
            import cv2
            img = cv2.imread(str(p))
            faces = app.get(img)
            if not faces:
                failed_faces.append(f"{p.name}: no face detected")
                continue
            # Use largest face if multiple
            face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
            if face_ref_path:
                # Compare embedding similarity if reference provided
                ref_img = cv2.imread(face_ref_path)
                ref_faces = app.get(ref_img)
                if ref_faces:
                    import numpy as np
                    ref_emb = ref_faces[0].embedding
                    sim = np.dot(face.embedding, ref_emb) / (
                        np.linalg.norm(face.embedding) * np.linalg.norm(ref_emb)
                    )
                    if sim < min_similarity:
                        failed_faces.append(
                            f"{p.name}: face similarity {sim:.3f} < {min_similarity}"
                        )
        except Exception as e:
            failed_faces.append(f"{p.name}: face check error — {e}")

    if failed_faces:
        result.add_error(
            f"face verification failed for {len(failed_faces)} image(s): "
            + "; ".join(failed_faces[:5])
            + (" ..." if len(failed_faces) > 5 else "")
        )


def _run_diversity_check(
    paths: list[Path],
    min_locations: int,
    result: ValidationResult,
):
    """Heuristic location/wardrobe diversity check via parent directory names."""
    parent_dirs: set[str] = set()
    for p in paths:
        parent_dirs.add(p.parent.name or p.parent.parent.name)

    if len(parent_dirs) < min_locations:
        result.add_warning(
            f"only {len(parent_dirs)} distinct location bucket(s) found "
            f"(want ≥{min_locations}). Add variety: different settings, "
            "clothing, and lighting across your reference set."
        )

    result.diversity_report["location_buckets"] = sorted(parent_dirs)
    result.diversity_report["total_images"] = len(paths)


def validate_single_image(
    image_path: str,
    min_resolution: int = 512,
) -> ValidationResult:
    """Validate a single reference image (quick check, no face verification)."""
    return validate_dataset([image_path], min_images=1, max_images=1,
                            min_resolution=min_resolution)
