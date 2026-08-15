import shutil
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.post import extract_frame, overlay_text


def test_overlay_text_passthrough_when_no_keywords():
    out = overlay_text(b"mp4", [], settings=MagicMock())
    assert out == b"mp4"


@patch("aeloria.generation.post.subprocess.run")
def test_overlay_text_burns_first_keyword(mock_run):
    mock_run.return_value = MagicMock(stdout=b"out-mp4", returncode=0)
    out = overlay_text(b"mp4", ["slow mornings", "forest"], settings=MagicMock())
    assert out == b"out-mp4"
    args = mock_run.call_args.args[0]
    assert "ffmpeg" in args[0]
    # drawtext filter references the first keyword only
    vf = [a for a in args if a.startswith("drawtext")]
    assert vf, "expected a drawtext filter argument"
    assert "slow mornings" in vf[0]


@patch("aeloria.generation.post.subprocess.run")
def test_extract_frame_seeks_to_timestamp(mock_run):
    mock_run.return_value = MagicMock(stdout=b"png", returncode=0)
    out = extract_frame(b"mp4", 4.0, settings=MagicMock())
    assert out == b"png"
    args = mock_run.call_args.args[0]
    assert "ffmpeg" in args[0]
    assert "4.0" in args or "00:00:04" in args


# ---- Unmocked ffmpeg smoke tests (pipe output must actually work) ----

_FFMPEG_ABSENT = shutil.which("ffmpeg") is None


def _ffmpeg_has_drawtext() -> bool:
    """overlay_text depends on the libfreetype-backed drawtext filter.
    Homebrew ffmpeg ships without it unless --with-freetype is set; skip those
    boxes rather than failing the suite on a Mac without that option."""
    if _FFMPEG_ABSENT:
        return False
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return False
    return "drawtext" in proc.stdout


def _tiny_mp4() -> bytes:
    """0.5s lavfi color source, fragmented mp4 to stdout (pipe-safe)."""
    proc = subprocess.run(
        ["ffmpeg", "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=0.5:r=10",
         "-f", "mp4", "-movflags", "frag_keyframe+empty_moov", "-"],
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")[:300]
    return proc.stdout


@pytest.mark.skipif(_FFMPEG_ABSENT, reason="ffmpeg binary not installed")
def test_overlay_text_real_ffmpeg_pipe_output():
    if not _ffmpeg_has_drawtext():
        pytest.skip("ffmpeg drawtext filter not available (rebuild ffmpeg with --with-freetype)")
    video = _tiny_mp4()
    out = overlay_text(video, ["smoke"], settings=MagicMock())
    assert isinstance(out, bytes) and len(out) > 0


@pytest.mark.skipif(_FFMPEG_ABSENT, reason="ffmpeg binary not installed")
def test_extract_frame_real_ffmpeg_pipe_output():
    video = _tiny_mp4()
    out = extract_frame(video, 0.2, settings=MagicMock())
    assert isinstance(out, bytes) and len(out) > 0
    assert out.startswith(b"\x89PNG")