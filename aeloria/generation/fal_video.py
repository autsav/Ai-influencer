"""fal.ai Kling image-to-video: animate a hero still (identity locked by the
flux-general + IP-Adapter path). i2v not t2v so Aeloria's face is preserved."""
import os

import fal_client
import httpx
from pydantic import BaseModel

from aeloria.config import Settings, get_settings


class VideoError(Exception):
    pass


class VideoResult(BaseModel):
    video_bytes: bytes
    cost_usd: float
    gen_params: dict


def generate_video(
    hero_image_url: str,
    prompt: str,
    settings: Settings | None = None,
    duration: int | None = None,
) -> VideoResult:
    s = settings or get_settings()
    os.environ["FAL_KEY"] = s.fal_key
    dur = duration if duration is not None else s.kling_video_duration
    arguments = {
        "image_url": hero_image_url,
        "prompt": prompt,
        "duration": str(dur),  # fal Kling DurationEnum expects "5"/"10" as a string
    }
    try:
        result = fal_client.subscribe(s.kling_model, arguments=arguments)
    except Exception as e:
        raise VideoError(f"fal video generation failed: {e}") from e
    video = (result or {}).get("video") or {}
    url = video.get("url")
    if not url:
        raise VideoError(f"fal returned no video url: {result}")

    resp = httpx.get(url, timeout=120)
    resp.raise_for_status()
    return VideoResult(
        video_bytes=resp.content,
        cost_usd=s.kling_video_cost_usd,
        gen_params={"model": s.kling_model, **arguments},
    )