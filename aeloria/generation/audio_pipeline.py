"""
Audio & lip-sync integration — voice cloning and lip alignment.

Stage 4 of the AI Influencer Pipeline.

Supports:
- Voice cloning via ElevenLabs API (primary)
- Voice cloning via XTTS v2 local (fallback)
- Lip-sync via Wav2Lip (if installed locally)
- Lip-sync via SadTalker (if installed locally)
- Audio generation fallback via LLM router (narration only)
"""
from __future__ import annotations

import os
import subprocess
import httpx
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class VoiceConfig:
    # ElevenLabs
    elevenlabs_api_key: str = ""
    voice_id: str = "EXAVITQu4vr4xnSDxMaL"  # default female voice
    stability: float = 0.5
    similarity_boost: float = 0.75
    # XTTS local
    xtts_model_path: str = ""  # path to local XTTS model if using fallback
    # Output
    output_format: str = "mp3"
    sample_rate: int = 44100


def generate_voice(
    text: str,
    output_path: str = "voice.mp3",
    config: VoiceConfig | None = None,
) -> str:
    """
    Generate voice audio from text using ElevenLabs (primary) or XTTS (fallback).
    
    Returns path to generated audio file.
    """
    cfg = config or VoiceConfig()
    
    # Try ElevenLabs first
    if cfg.elevenlabs_api_key:
        try:
            return _elevenlabs_tts(text, output_path, cfg)
        except Exception as e:
            print(f"[audio] ElevenLabs failed: {e} — trying fallback")
    
    # Fallback: XTTS v2 local
    if cfg.xtts_model_path and Path(cfg.xtts_model_path).exists():
        try:
            return _xtts_tts(text, output_path, cfg)
        except Exception as e:
            print(f"[audio] XTTS failed: {e}")
    
    # Last resort: use LLM router for narration (no actual voice, just text)
    raise RuntimeError(
        "No voice cloning available. Set ELEVENLABS_API_KEY in .env or install XTTS v2.\n"
        "Get ElevenLabs key: https://elevenlabs.io\n"
        "Install XTTS: pip install TTS && tts --model xtts_v2"
    )


def _elevenlabs_tts(text: str, output_path: str, cfg: VoiceConfig) -> str:
    """Generate voice via ElevenLabs API."""
    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{cfg.voice_id}",
        headers={
            "xi-api-key": cfg.elevenlabs_api_key,
            "Content-Type": "application/json",
        },
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": cfg.stability,
                "similarity_boost": cfg.similarity_boost,
            },
        },
        timeout=60,
    )
    resp.raise_for_status()
    
    with open(output_path, "wb") as f:
        f.write(resp.content)
    
    print(f"[audio] ✅ ElevenLabs voice: {output_path} ({len(resp.content)/1e6:.1f} MB)")
    return output_path


def _xtts_tts(text: str, output_path: str, cfg: VoiceConfig) -> str:
    """Generate voice via local XTTS v2."""
    cmd = [
        "tts",
        "--model", "tts_models/multilingual/multi-dataset/xtts_v2",
        "--text", text,
        "--out_path", output_path,
        "--language_idx", "en",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"XTTS failed: {result.stderr[-300:]}")
    print(f"[audio] ✅ XTTS voice: {output_path}")
    return output_path


def lip_sync(
    image_path: str,
    audio_path: str,
    output_path: str = "lip_synced.mp4",
    method: str = "wav2lip",
) -> str:
    """
    Apply lip-sync to a static image using Wav2Lip or SadTalker.
    
    Args:
        image_path: Source face image
        audio_path: Voice audio file
        output_path: Output video path
        method: "wav2lip" or "sadtalker"
    
    Returns:
        Path to lip-synced video
    """
    if method == "wav2lip":
        return _wav2lip(image_path, audio_path, output_path)
    elif method == "sadtalker":
        return _sadtalker(image_path, audio_path, output_path)
    else:
        raise ValueError(f"Unknown method: {method}")


def _wav2lip(image_path: str, audio_path: str, output_path: str) -> str:
    """Run Wav2Lip for lip-sync."""
    # Check if Wav2Lip is installed
    wav2lip_path = Path.home() / "Wav2Lip" / "inference.py"
    if not wav2lip_path.exists():
        raise RuntimeError(
            "Wav2Lip not installed. Clone:\n"
            "  git clone https://github.com/Rudrabha/Wav2Lip ~/Wav2Lip\n"
            "  cd ~/Wav2Lip && pip install -r requirements.txt\n"
            "  Download checkpoint to ~/Wav2Lip/checkpoints/wav2lip.pth"
        )
    
    cmd = [
        "python", str(wav2lip_path),
        "--checkpoint_path", str(wav2lip_path.parent / "checkpoints" / "wav2lip.pth"),
        "--face", image_path,
        "--audio", audio_path,
        "--outfile", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Wav2Lip failed: {result.stderr[-300:]}")
    print(f"[audio] ✅ Wav2Lip: {output_path}")
    return output_path


def _sadtalker(image_path: str, audio_path: str, output_path: str) -> str:
    """Run SadTalker for lip-sync."""
    sadtalker_path = Path.home() / "SadTalker"
    if not sadtalker_path.exists():
        raise RuntimeError(
            "SadTalker not installed. Clone:\n"
            "  git clone https://github.com/OpenTalker/SadTalker ~/SadTalker\n"
            "  cd ~/SadTalker && pip install -r requirements.txt"
        )
    
    cmd = [
        "python", "inference.py",
        "--driven_audio", audio_path,
        "--source_image", image_path,
        "--result_dir", str(Path(output_path).parent),
        "--enhancer", "gfpgan",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(sadtalker_path))
    if result.returncode != 0:
        raise RuntimeError(f"SadTalker failed: {result.stderr[-300:]}")
    print(f"[audio] ✅ SadTalker: {output_path}")
    return output_path


def generate_srt_subtitles(
    text: str,
    audio_duration: float,
    output_path: str = "subtitles.srt",
) -> str:
    """
    Generate a simple .srt subtitle file from text, distributing evenly across audio duration.
    """
    # Split text into ~5 word chunks
    words = text.split()
    chunks = []
    current_chunk = []
    for w in words:
        current_chunk.append(w)
        if len(current_chunk) >= 5:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    # Time per chunk
    chunk_duration = audio_duration / max(len(chunks), 1)
    
    with open(output_path, "w") as f:
        for i, chunk in enumerate(chunks):
            start = i * chunk_duration
            end = (i + 1) * chunk_duration
            f.write(f"{i+1}\n")
            f.write(f"{_format_time(start)} --> {_format_time(end)}\n")
            f.write(f"{chunk}\n\n")
    
    print(f"[audio] ✅ Subtitles: {output_path} ({len(chunks)} segments)")
    return output_path


def _format_time(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"