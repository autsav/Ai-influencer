"""Video generation: animate an identity-locked still via Kling i2v.

Thin wrapper over fal_video.generate_video — returns the raw VideoResult
(video_bytes, cost_usd, gen_params). The face-gate / overlay / retry loop
lives in generation.worker so cost rows are tracked even when post-processing
fails; this module just produces the raw Kling output."""

import logging

from aeloria.generation.fal_video import VideoResult, generate_video

log = logging.getLogger(__name__)


def produce_video(still_url: str, prompt: str, settings) -> VideoResult:
    """Animate the hero still via Kling i2v. Returns the raw VideoResult;
    the caller owns the video face-gate, overlay, and retry loop."""
    return generate_video(still_url, prompt, settings=settings)