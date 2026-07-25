import json
from functools import lru_cache
from pathlib import Path

import numpy as np


class FaceGateError(Exception):
    pass


@lru_cache
def _analyzer():
    from insightface.app import FaceAnalysis

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


def embed_face(image_bytes: bytes) -> np.ndarray:
    import cv2

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise FaceGateError("cannot decode image")
    faces = _analyzer().get(img)
    if not faces:
        raise FaceGateError("no face detected")
    faces.sort(
        key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
        reverse=True,
    )
    return faces[0].normed_embedding


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def load_reference(path: str) -> np.ndarray:
    data = json.loads(Path(path).read_text())
    return np.asarray(data["embedding"], dtype=np.float32)


def passes_gate(image_bytes: bytes, ref: np.ndarray, threshold: float) -> tuple[float, bool]:
    emb = embed_face(image_bytes)
    sim = similarity(emb, ref)
    return sim, sim >= threshold
