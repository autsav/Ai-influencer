"""Multi-reference face loader: rotates through reference face images.

Supports loading multiple reference face images (different angles, distances,
lighting) from a directory. PuLID works best with diverse reference angles —
using a single image limits identity lock for extreme angles (profile, top-down).

Usage:
    from aeloria.generation.face_refs import load_reference_faces, select_reference_face
    faces = load_reference_faces("aeloria/persona/reference_faces")
    ref = select_reference_face(faces, seed=42)
"""
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

_VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def load_reference_faces(ref_dir: str) -> list[bytes]:
    """Load all image files from the reference faces directory.

    Returns an empty list if the directory doesn't exist or has no images.
    Files are sorted by name for deterministic ordering.
    """
    p = Path(ref_dir)
    if not p.exists():
        log.debug("Reference faces directory %s does not exist", ref_dir)
        return []

    faces = []
    for f in sorted(p.iterdir()):
        if f.is_file() and f.suffix.lower() in _VALID_EXTENSIONS:
            faces.append(f.read_bytes())

    log.info("Loaded %d reference faces from %s", len(faces), ref_dir)
    return faces


def select_reference_face(
    faces: list[bytes], seed: int | None = None
) -> bytes | None:
    """Select a reference face by seed (deterministic rotation) or random.

    If seed is provided, selection is deterministic: faces[seed % len(faces)].
    If seed is None, picks randomly.
    Returns None if the list is empty.
    """
    if not faces:
        return None

    if seed is not None:
        return faces[seed % len(faces)]

    import random

    return random.choice(faces)