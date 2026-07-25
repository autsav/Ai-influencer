"""Async voice & lip-sync stage — ElevenLabs + SyncLabs/Hedra.

Wraps the existing aeloria.generation.audio_pipeline for async pipeline use.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from pipeline.config_loader import VoiceConfig

logger = logging.getLogger(__name__)


@dataclass
class VoiceResult:
    audio_bytes: bytes
    audio_path: str = ""
    video_path: str = ""
    cost_usd: float = 0.0
    gen_time: float = 0.0


async def generate_voice(
    text: str,
    config: VoiceConfig,
    output_path: str = "output/voice.mp3",
    dry_run: bool = False,
) -> VoiceResult:
    """Generate voice audio via ElevenLabs (primary) or return empty on dry run."""
    if dry_run:
        logger.info("Dry run — skipping voice generation")
        return VoiceResult(audio_bytes=b"", gen_time=0.0)

    if not config.elevenlabs_api_key:
        logger.warning("No ElevenLabs API key — skipping voice")
        return VoiceResult(audio_bytes=b"")

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None, _elevenlabs_tts, text, config, output_path
    )
    return result


def _elevenlabs_tts(text: str, config: VoiceConfig, output_path: str) -> VoiceResult:
    """Blocking ElevenLabs TTS call."""
    t0 = time.time()
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.voice_id}"

    headers = {
        "xi-api-key": config.elevenlabs_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": config.stability,
            "similarity_boost": config.similarity_boost,
        },
    }

    with httpx.Client(timeout=60) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        audio_bytes = resp.content

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    elapsed = time.time() - t0
    logger.info("Voice generated in %.1fs → %s", elapsed, output_path)
    return VoiceResult(
        audio_bytes=audio_bytes,
        audio_path=output_path,
        cost_usd=0.18,  # ElevenLabs per-character pricing estimate
        gen_time=elapsed,
    )


async def generate_lip_sync(
    image_bytes: bytes,
    audio_bytes: bytes,
    config: VoiceConfig,
    output_path: str = "output/lipsync.mp4",
    dry_run: bool = False,
) -> str:
    """Generate lip-synced video via SyncLabs or Hedra.

    Returns path to generated video, or empty string if not configured.
    """
    if dry_run or not (config.synclabs_api_key or config.hedra_api_key):
        logger.info("Lip-sync skipped (no API key or dry run)")
        return ""

    if config.synclabs_api_key:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _synclabs_lipsync, image_bytes, audio_bytes, config, output_path
        )
    if config.hedra_api_key:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, _hedra_lipsync, image_bytes, audio_bytes, config, output_path
        )
    return ""


def _synclabs_lipsync(
    image_bytes: bytes, audio_bytes: bytes, config: VoiceConfig, output_path: str
) -> str:
    """SyncLabs lip-sync API (async submission + polling)."""
    import tempfile

    t0 = time.time()
    headers = {"Authorization": f"Bearer {config.synclabs_api_key}"}

    with httpx.Client(timeout=120) as client:
        # Upload image and audio
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_tmp:
            img_tmp.write(image_bytes)
            img_tmp.flush()
            img_resp = client.post(
                "https://api.synclabs.so/upload",
                headers=headers,
                files={"file": ("image.png", open(img_tmp.name, "rb"), "image/png")},
            )
            img_resp.raise_for_status()
            image_url = img_resp.json()["url"]

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as aud_tmp:
            aud_tmp.write(audio_bytes)
            aud_tmp.flush()
            aud_resp = client.post(
                "https://api.synclabs.so/upload",
                headers=headers,
                files={"file": ("audio.mp3", open(aud_tmp.name, "rb"), "audio/mpeg")},
            )
            aud_resp.raise_for_status()
            audio_url = aud_resp.json()["url"]

        # Submit lip-sync job
        job_resp = client.post(
            "https://api.synclabs.so/lip-sync",
            headers=headers,
            json={"imageUrl": image_url, "audioUrl": audio_url, "model": "sync-1.6.0"},
        )
        job_resp.raise_for_status()
        job_id = job_resp.json()["id"]

        # Poll until complete
        for _ in range(60):
            import time as _time
            _time.sleep(5)
            status_resp = client.get(
                f"https://api.synclabs.so/lip-sync/{job_id}", headers=headers
            )
            status_resp.raise_for_status()
            data = status_resp.json()
            if data.get("status") == "COMPLETED":
                video_url = data.get("videoUrl", "")
                if video_url:
                    video_resp = client.get(video_url)
                    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                    with open(output_path, "wb") as f:
                        f.write(video_resp.content)
                    logger.info("Lip-sync completed in %.1fs", time.time() - t0)
                    return output_path
            elif data.get("status") == "FAILED":
                logger.error("SyncLabs job failed: %s", data)
                return ""
    return ""


def _hedra_lipsync(
    image_bytes: bytes, audio_bytes: bytes, config: VoiceConfig, output_path: str
) -> str:
    """Hedra lip-sync API (placeholder — implement when API key available)."""
    logger.warning("Hedra lip-sync not yet implemented")
    return ""