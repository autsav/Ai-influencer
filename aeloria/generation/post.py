"""ffmpeg post-processing for Reels. v1: burn the hook on-screen keyword (first
3s) + extract a late frame for the video face-gate. No audio work (master spec
marks audio overlay phase 2). Degrades loudly on ffmpeg failure."""
import os
import subprocess
import tempfile

from aeloria.config import Settings

FFMPEG = "ffmpeg"


class PostError(Exception):
    pass


def overlay_text(video_bytes: bytes, keywords: list[str], settings: Settings) -> bytes:
    if not keywords:
        return video_bytes
    text = keywords[0]
    vf = (
        f"drawtext=text='{text}':x=(w-text_w)/2:y=h*0.12:fontsize=48:"
        f"fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=8:"
        f"enable='between(t,0,3)'"
    )
    # Fragmented mp4: the plain mp4 muxer (and +faststart) needs seekable
    # output and fails on a stdout pipe; frag_keyframe+empty_moov streams.
    proc = subprocess.run(
        [FFMPEG, "-i", "-", "-vf", vf, "-f", "mp4",
         "-movflags", "frag_keyframe+empty_moov", "-"],
        input=video_bytes, capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise PostError(f"ffmpeg overlay failed: {proc.stderr.decode(errors='replace')[:200]}")
    return proc.stdout


def extract_frame(video_bytes: bytes, t_seconds: float, settings: Settings) -> bytes:
    # Provider MP4s (e.g. fal Kling) are not always faststart, so demuxing from a
    # non-seekable stdin pipe can fail to locate the moov atom and the -ss seek
    # returns no frame. Write to a seekable temp file so the seek is reliable.
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
        tf.write(video_bytes)
        path = tf.name
    try:
        proc = subprocess.run(
            [FFMPEG, "-ss", str(t_seconds), "-i", path, "-frames:v", "1",
             "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True,
        )
        if proc.returncode != 0 or not proc.stdout:
            raise PostError(f"ffmpeg extract_frame failed: {proc.stderr.decode(errors='replace')[:800]}")
        return proc.stdout
    finally:
        os.unlink(path)


def overlay_image_text(image_bytes: bytes, text: str, settings: Settings) -> bytes:
    """Burn a single line of overlay text onto a still image. Pipe-safe PNG in/out.
    Empty text returns the input unchanged."""
    if not text:
        return image_bytes
    safe = text.replace(":", r"\:").replace("'", r"\'")
    vf = (
        f"drawtext=text='{safe}':fontcolor=white:fontsize=48:"
        f"box=1:boxcolor=black@0.5:boxborderw=12:x=(w-text_w)/2:y=h-th-80"
    )
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", "pipe:0", "-vf", vf, "-f", "image2", "-vcodec", "png", "pipe:1"],
        input=image_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise PostError(f"overlay_image_text ffmpeg failed rc={proc.returncode}: {proc.stderr[:200]!r}")
    return proc.stdout