"""Lip-sync video generation via fal.ai.

Animates a still/video with synchronized lip movement from an audio track.
Uses fal-ai/wav2lip for talking-head reels — enables Aeloria to "speak"
in Reels with accurate lip-sync.

Usage:
    from aeloria.generation.lipsync import lip_sync_video
    result = lip_sync_video(
        video_url="https://r2.dev/video.mp4",
        audio_url="https://r2.dev/audio.wav",
        settings=settings,
    )
    if result.video_bytes:
        # Upload lip-synced video
"""
import logging
import httpx

log = logging.getLogger(__name__)

# fal.ai lip-sync endpoint — Wav2Lip
LIPSYNC_MODEL = "fal-ai/wav2lip"
LIPSYNC_COST_USD = 0.15


class LipSyncResult:
    """Result of a lip-sync generation."""

    def __init__(
        self,
        video_bytes: bytes | None,
        cost_usd: float = 0.0,
        gen_params: dict | None = None,
    ):
        self.video_bytes = video_bytes
        self.cost_usd = cost_usd
        self.gen_params = gen_params or {}


def lip_sync_video(
    video_url: str,
    audio_url: str | None,
    settings,
    face_detect_boost: bool = True,
    pad_size: int = 10,
) -> LipSyncResult:
    """Generate a lip-synced video from a source video + audio track.

    The source video (typically a Kling i2v output) is combined with an audio
    track to produce a video where Aeloria's lips move in sync with the audio.

    Args:
        video_url: Public URL to the source MP4 video
        audio_url: Public URL to the audio track (WAV/MP3). If None, returns
                   empty result (lip-sync is optional — skip gracefully).
        settings: App settings (needs fal_key)
        face_detect_boost: Enhance face detection accuracy
        pad_size: Padding around detected face (pixels)

    Returns:
        LipSyncResult with video_bytes (or None if skipped/failed),
        cost_usd, and gen_params.
    """
    if not audio_url:
        log.info("Lip-sync skipped: no audio track provided")
        return LipSyncResult(video_bytes=None, cost_usd=0.0)

    import os
    import fal_client

    os.environ["FAL_KEY"] = settings.fal_key

    arguments = {
        "video_url": video_url,
        "audio_url": audio_url,
        "face_detect_boost": face_detect_boost,
        "pad_size": pad_size,
    }

    log.info("Lip-sync generation: model=%s, video=%s", LIPSYNC_MODEL, video_url)

    try:
        result = fal_client.subscribe(LIPSYNC_MODEL, arguments=arguments)
        video_url_out = result.get("video", {}).get("url")
        if not video_url_out:
            # Try alternate response format
            video_url_out = result.get("output", {}).get("video_url")
        if not video_url_out:
            raise RuntimeError(f"Lip-sync returned no video URL: {result}")

        resp = httpx.get(video_url_out, timeout=120)
        resp.raise_for_status()

        log.info("Lip-sync complete: cost=$%.4f, %d bytes", LIPSYNC_COST_USD, len(resp.content))
        return LipSyncResult(
            video_bytes=resp.content,
            cost_usd=LIPSYNC_COST_USD,
            gen_params={"model": LIPSYNC_MODEL, **arguments},
        )
    except Exception as e:
        log.error("Lip-sync failed: %s", e)
        return LipSyncResult(video_bytes=None, cost_usd=0.0)