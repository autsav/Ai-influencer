"""
FFmpeg rendering pipeline — assembles final video outputs.

Stitches image + voice + subtitles + music into 1080x1920 60fps vertical video.
"""
from __future__ import annotations

import subprocess
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class RenderConfig:
    width: int = 1080
    height: int = 1920
    fps: int = 60
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 18           # quality (lower = better, 18 is visually lossless)
    preset: str = "medium"  # encoding speed (slower = smaller file)


def render_image_to_video(
    image_path: str,
    audio_path: str | None = None,
    subtitle_path: str | None = None,
    music_path: str | None = None,
    duration: float = 5.0,
    output_path: str = "output.mp4",
    config: RenderConfig | None = None,
) -> str:
    """
    Render a static image into a vertical video with optional audio/subtitles/music.
    
    Args:
        image_path: Path to source image (any format)
        audio_path: Path to voice/narration audio (wav/mp3)
        subtitle_path: Path to .srt subtitle file
        music_path: Path to background music (volume auto-ducked under voice)
        duration: Video duration in seconds (ignored if audio provided)
        output_path: Output mp4 path
        config: Render settings
    
    Returns:
        Path to rendered video
    """
    cfg = config or RenderConfig()
    
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Build FFmpeg command
    cmd = ["ffmpeg", "-y"]
    
    # Input: image (loop to create video stream)
    cmd.extend(["-loop", "1", "-i", image_path])
    
    # Input: voice audio (if provided)
    if audio_path and Path(audio_path).exists():
        cmd.extend(["-i", audio_path])
    
    # Input: background music (if provided)
    if music_path and Path(music_path).exists():
        cmd.extend(["-i", music_path])
    
    # Duration
    if audio_path and Path(audio_path).exists():
        cmd.extend(["-shortest"])  # match audio length
    else:
        cmd.extend(["-t", str(duration)])
    
    # Filters: scale + crop to vertical, Ken Burns zoom effect
    zoom_filter = (
        f"scale={cfg.width}:{cfg.height}:force_original_aspect_ratio=increase,"
        f"crop={cfg.width}:{cfg.height},"
        f"zoompan=z='min(zoom+0.0008,1.15)':d={int(duration * cfg.fps)}:s={cfg.width}x{cfg.height}:fps={cfg.fps}"
    )
    cmd.extend(["-vf", zoom_filter])
    
    # Audio mixing: if both voice and music, duck music under voice
    if audio_path and music_path and Path(audio_path).exists() and Path(music_path).exists():
        # Voice on track 0, music on track 1 — duck music to 15% volume
        cmd.extend([
            "-filter_complex",
            f"[1:a]volume=1.0[voice];[2:a]volume=0.15[bgm];[voice][bgm]amix=inputs=2:duration=first[aout]",
            "-map", "0:v", "-map", "[aout]",
        ])
    elif audio_path and Path(audio_path).exists():
        cmd.extend(["-map", "0:v", "-map", "1:a"])
    else:
        cmd.extend(["-map", "0:v"])
    
    # Subtitles (burn in)
    if subtitle_path and Path(subtitle_path).exists():
        cmd.extend(["-vf", f"subtitles={subtitle_path}"])
    
    # Output settings
    cmd.extend([
        "-c:v", cfg.video_codec,
        "-preset", cfg.preset,
        "-crf", str(cfg.crf),
        "-r", str(cfg.fps),
        "-pix_fmt", "yuv420p",
        "-c:a", cfg.audio_codec,
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ])
    
    print(f"[render] Running FFmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
    
    size = os.path.getsize(output_path) / 1e6
    print(f"[render] ✅ Output: {output_path} ({size:.1f} MB)")
    return output_path


def render_carousel_video(
    image_paths: list[str],
    audio_path: str | None = None,
    output_path: str = "carousel.mp4",
    slide_duration: float = 3.0,
    config: RenderConfig | None = None,
) -> str:
    """
    Render multiple images into a slideshow video with crossfade transitions.
    """
    cfg = config or RenderConfig()
    
    if not image_paths:
        raise ValueError("No images provided")
    
    # Create a concat file for FFmpeg
    concat_path = "/tmp/aeloria_concat.txt"
    with open(concat_path, "w") as f:
        for img in image_paths:
            f.write(f"file '{img}'\nduration {slide_duration}\n")
        f.write(f"file '{image_paths[-1]}'\n")  # repeat last
    
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-vf", f"scale={cfg.width}:{cfg.height}:force_original_aspect_ratio=increase,crop={cfg.width}:{cfg.height}",
        "-c:v", cfg.video_codec,
        "-preset", cfg.preset,
        "-crf", str(cfg.crf),
        "-r", str(cfg.fps),
        "-pix_fmt", "yuv420p",
    ]
    
    if audio_path and Path(audio_path).exists():
        cmd.extend(["-i", audio_path, "-shortest", "-c:a", cfg.audio_codec, "-b:a", "192k"])
    
    cmd.extend(["-movflags", "+faststart", output_path])
    
    print(f"[render] Building carousel video from {len(image_paths)} images...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")
    
    size = os.path.getsize(output_path) / 1e6
    print(f"[render] ✅ Carousel: {output_path} ({size:.1f} MB)")
    return output_path


def check_ffmpeg() -> bool:
    """Check if FFmpeg is installed."""
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False