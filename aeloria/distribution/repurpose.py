"""Content repurposing: reformat one IG post for TikTok, LinkedIn, X, email.

Takes the canonical IG post (image + caption) and produces platform-specific
variants: aspect-ratio reformatted image, platform-tuned caption, and
X thread splits.

Usage:
    from aeloria.distribution.repurpose import repurpose_post
    result = repurpose_post(
        image_url="https://r2.dev/img.png",
        video_url="https://r2.dev/vid.mp4",
        caption="Found this AI tool 🔥\\n\\n#AI #Tech",
        pillar="ai_tools",
    )
    # result.platforms["tiktok"]["caption"] — 150-char truncated
    # result.platforms["linkedin"]["caption"] — hashtags stripped, professional
    # result.platforms["x"]["caption"] — list of thread tweets
    # result.platforms["email"]["caption"] — full text, no hashtags
"""
import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Platform specifications
PLATFORM_SPECS = {
    "instagram": {
        "aspect": "4:5",
        "caption_limit": 2200,
        "hashtags": True,
        "media_type": "image_or_video",
    },
    "tiktok": {
        "aspect": "9:16",
        "caption_limit": 150,
        "hashtags": True,
        "media_type": "video",
    },
    "linkedin": {
        "aspect": "1.91:1",
        "caption_limit": 3000,
        "hashtags": False,
        "media_type": "image",
    },
    "x": {
        "aspect": "16:9",
        "caption_limit": 280,
        "hashtags": False,
        "media_type": "image",
        "thread": True,
    },
    "email": {
        "aspect": None,
        "caption_limit": None,
        "hashtags": False,
        "media_type": "none",
    },
}


@dataclass
class RepurposeResult:
    """Result of repurposing a post across platforms."""
    platforms: dict = field(default_factory=dict)
    # {platform: {"aspect": str|None, "caption": str|list[str], "media_url": str|None, "needs_reformat": bool}}


def reformat_aspect_ratio(source_ratio: str, target_ratio: str) -> str:
    """Return the target aspect ratio string.

    Actual reformatting (cropping/padding) is done downstream by fal.ai
    or PIL post-processing. This function is a spec lookup.
    """
    return target_ratio


def _strip_hashtags(caption: str) -> str:
    """Remove hashtag lines from a caption."""
    lines = caption.split("\n")
    clean = [l for l in lines if not l.strip().startswith("#")]
    return "\n".join(clean).strip()


def _split_x_thread(caption: str, limit: int = 280) -> list[str]:
    """Split a long caption into an X/Twitter thread (max 280 chars per tweet)."""
    if len(caption) <= limit:
        return [caption]

    # Split on sentence boundaries first, then on spaces
    import re
    sentences = re.split(r'(?<=[.!?])\s+', caption.replace("\n", " ").strip())

    threads = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 <= limit:
            current = f"{current} {s}".strip()
        else:
            if current:
                threads.append(current)
            # If a single sentence is too long, hard-split into chunks
            while len(s) > limit:
                threads.append(s[:limit])
                s = s[limit:]
            current = s
    if current:
        threads.append(current)

    return threads


def adapt_caption_for_platform(caption: str, platform: str) -> str | list[str]:
    """Adapt caption for platform conventions.

    - LinkedIn: strip hashtags, keep professional tone
    - X/Twitter: split into thread if > 280 chars
    - TikTok: truncate to 150 chars
    - Email: full text, no hashtags
    - Instagram: unchanged (canonical)
    """
    spec = PLATFORM_SPECS.get(platform, {})
    limit = spec.get("caption_limit")
    use_hashtags = spec.get("hashtags", True)
    is_thread = spec.get("thread", False)

    if not use_hashtags:
        caption = _strip_hashtags(caption)

    if platform == "x" and is_thread and limit:
        return _split_x_thread(caption, limit)

    if limit and len(caption) > limit:
        return caption[:limit - 3] + "..."

    return caption


def repurpose_post(
    image_url: str | None = None,
    video_url: str | None = None,
    caption: str = "",
    pillar: str = "",
) -> RepurposeResult:
    """Repurpose a canonical IG post for all platforms.

    Args:
        image_url: Public URL to the image (R2)
        video_url: Public URL to the video if it's a reel (R2)
        caption: The canonical Instagram caption
        pillar: Content pillar (for future analytics tracking)

    Returns:
        RepurposeResult with per-platform specs
    """
    result = RepurposeResult()

    for platform, spec in PLATFORM_SPECS.items():
        adapted = adapt_caption_for_platform(caption, platform)

        # Video platforms get video, image platforms get image
        media = None
        if spec["media_type"] == "video" and video_url:
            media = video_url
        elif spec["media_type"] in ("image", "image_or_video"):
            media = video_url if video_url else image_url

        result.platforms[platform] = {
            "aspect": spec["aspect"],
            "caption": adapted,
            "media_url": media,
            "needs_reformat": spec["aspect"] is not None,
            "pillar": pillar,
        }

    log.info("Repurposed post for %d platforms (%s)", len(result.platforms), pillar)
    return result