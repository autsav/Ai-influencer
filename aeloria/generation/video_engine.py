"""
Kling 3.0 / Wan 2.5 image-to-video engine.

Uses the Image-to-Video Anchor Method: a face-verified hero still is passed
to the video API with ONLY camera-movement instructions (no Aeloria physical
description) to prevent identity drift.
"""

import io
import logging
from dataclasses import dataclass, field
from typing import Literal

import httpx

from aeloria.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Supported video engines
VideoEngine = Literal["kling", "wan"]


@dataclass
class VideoEngineConfig:
    """Runtime config for the video engine."""

    engine: VideoEngine = "kling"
    kling_api_key: str = ""
    wan_api_key: str = ""
    model: str = "kling-video/v2.5-turbo/pro/image-to-video"
    duration: int = 5  # seconds; fal-ai wants "5" or "10" as string
    prompt: str = ""  # camera movement only — never Aeloria's physical description
    image_bytes: bytes = field(default=b"", repr=False)
    cfg_strength: float = 0.5  # how closely video follows the image

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "VideoEngineConfig":
        s = settings or get_settings()
        return cls(
            kling_api_key=s.kling_api_key,
            wan_api_key=s.wan_api_key,
            model=s.kling_model,
            duration=s.kling_video_duration,
        )


def _kling_generate(cfg: VideoEngineConfig) -> bytes:
    """
    Generate video via fal.ai's Kling 3.0 image-to-video endpoint.

    The image is uploaded as a temporary fal storage URL, then Kling is called
    with ONLY camera-movement instructions in the prompt.
    """
    if not cfg.kling_api_key:
        raise RuntimeError(
            "Kling API key not configured. Set KLING_API_KEY in .env"
        )

    # 1 — upload image to fal so we get a URL
    with httpx.Client(timeout=60.0) as client:
        # Upload image bytes to fal's temporary storage
        upload_resp = client.post(
            "https://api.fal.ai/files",
            headers={"Authorization": f"Key {cfg.kling_api_key}"},
            data={"content_type": "image/jpeg"},
            files={"file": ("image.jpg", cfg.image_bytes, "image/jpeg")},
        )
        upload_resp.raise_for_status()
        image_url = upload_resp.json()["url"]

    # 2 — call Kling image-to-video
    payload = {
        "image_url": image_url,
        "prompt": cfg.prompt,
        "duration": str(cfg.duration),  # fal wants string "5" or "10"
        "cfg_scale": cfg.cfg_strength,
    }

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"https://api.fal.ai/{cfg.model}",
            headers={"Authorization": f"Key {cfg.kling_api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()

    video_url = result.get("video", {}).get("url") or result.get("url")
    if not video_url:
        raise RuntimeError(f"Kling returned no video URL: {result}")

    # 3 — download the generated video
    with httpx.Client(timeout=120.0) as client:
        video_resp = client.get(video_url)
        video_resp.raise_for_status()

    logger.info("Kling video generated: %s (%d bytes)", video_url, len(video_resp.content))
    return video_resp.content


def _wan_generate(cfg: VideoEngineConfig) -> bytes:
    """Generate video via Wan 2.5 API."""
    if not cfg.wan_api_key:
        raise RuntimeError("Wan API key not configured. Set WAN_API_KEY in .env")

    # Wan 2.5 uses a different payload shape — adjust as needed for actual API
    payload = {
        "image": io.BytesIO(cfg.image_bytes),
        "prompt": cfg.prompt,
        "duration": cfg.duration,
        "cfg_strength": cfg.cfg_strength,
    }

    # Placeholder — replace with actual Wan API endpoint and auth
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            "https://api.wan.video/v2.5/image-to-video",
            headers={"Authorization": f"Bearer {cfg.wan_api_key}"},
            data=payload,  # may need multipart; adjust to Wan API spec
        )
        resp.raise_for_status()
        result = resp.json()

    video_url = result.get("video_url") or result.get("output")
    if not video_url:
        raise RuntimeError(f"Wan returned no video URL: {result}")

    with httpx.Client(timeout=120.0) as client:
        video_resp = client.get(video_url)
        video_resp.raise_for_status()

    logger.info("Wan video generated: %s (%d bytes)", video_url, len(video_resp.content))
    return video_resp.content


def generate_video(
    image_bytes: bytes,
    prompt: str,
    engine: VideoEngine = "kling",
    settings: Settings | None = None,
    duration: int = 5,
    cfg_strength: float = 0.5,
) -> bytes:
    """
    Generate a short video from a face-verified hero still using the
    Image-to-Video Anchor Method.

    Args:
        image_bytes:  Face-verified hero still (JPEG/PNG).
        prompt:       Camera movement instructions ONLY.
                      e.g. "slow orbit, wind gently blowing through hair"
                      NEVER include Aeloria's physical description.
        engine:      "kling" (default) or "wan".
        settings:     Optional Settings override.
        duration:     Video length in seconds (5 or 10).
        cfg_strength: How closely the video follows the image (0.0–1.0).

    Returns:
        Raw video bytes (MP4).
    """
    cfg = VideoEngineConfig(
        engine=engine,
        image_bytes=image_bytes,
        prompt=prompt,
        duration=duration,
        cfg_strength=cfg_strength,
    )
    # Merge in API keys from settings
    cfg.kling_api_key = (
        settings.kling_api_key if settings else get_settings().kling_api_key
    )
    cfg.wan_api_key = (
        settings.wan_api_key if settings else get_settings().wan_api_key
    )
    cfg.model = (settings.kling_model if settings else get_settings().kling_model) if engine == "kling" else ""

    if engine == "kling":
        return _kling_generate(cfg)
    elif engine == "wan":
        return _wan_generate(cfg)
    else:
        raise ValueError(f"Unknown video engine: {engine}. Use 'kling' or 'wan'.")
