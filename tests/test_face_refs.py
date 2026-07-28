"""Tests for multi-reference face loader."""
import pytest
from pathlib import Path

from aeloria.generation.face_refs import load_reference_faces, select_reference_face


def test_load_reference_faces_empty_dir(tmp_path):
    assert load_reference_faces(str(tmp_path)) == []


def test_load_reference_faces_nonexistent_dir():
    assert load_reference_faces("/nonexistent/path/12345") == []


def test_load_reference_faces_loads_images(tmp_path):
    (tmp_path / "front.jpg").write_bytes(b"img1")
    (tmp_path / "profile.png").write_bytes(b"img2")
    (tmp_path / "readme.txt").write_bytes(b"skip")
    faces = load_reference_faces(str(tmp_path))
    assert len(faces) == 2
    assert faces[0] == b"img1"
    assert faces[1] == b"img2"


def test_load_reference_faces_sorted(tmp_path):
    (tmp_path / "c_profile.png").write_bytes(b"c")
    (tmp_path / "a_front.jpg").write_bytes(b"a")
    (tmp_path / "b_side.jpeg").write_bytes(b"b")
    faces = load_reference_faces(str(tmp_path))
    assert faces[0] == b"a"  # a_front comes first alphabetically
    assert faces[2] == b"c"


def test_select_reference_face_by_seed():
    faces = [b"a", b"b", b"c"]
    assert select_reference_face(faces, seed=0) == b"a"
    assert select_reference_face(faces, seed=1) == b"b"
    assert select_reference_face(faces, seed=2) == b"c"
    assert select_reference_face(faces, seed=3) == b"a"  # wraps around
    assert select_reference_face(faces, seed=42) == b"a"  # 42 % 3 = 0


def test_select_reference_face_empty():
    assert select_reference_face([], seed=42) is None
    assert select_reference_face([], seed=None) is None


def test_select_reference_face_random():
    faces = [b"a", b"b", b"c"]
    result = select_reference_face(faces, seed=None)
    assert result in faces


def test_select_reference_face_single():
    faces = [b"only"]
    assert select_reference_face(faces, seed=0) == b"only"
    assert select_reference_face(faces, seed=999) == b"only"