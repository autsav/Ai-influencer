"""TikTok Content Posting API — publish reels as TikTok videos.

Uses the TikTok Content Posting API (v2) for direct video posting via
PULL_FROM_URL. Requires TikTok Login Kit credentials (client_key,
client_secret, access_token, open_id) obtained via OAuth flow.

Reference: https://developers.tiktok.com/doc/content-posting-api
"""
import logging
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

log = logging.getLogger(__name__)

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokError(Exception):
    pass


def _retryable(exc) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    if isinstance(exc, TikTokError):
        return False
    return False


_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=15, min=15, max=120),
    retry=retry_if_exception(_retryable),
    retry_error_callback=lambda s: s.outcome.result(),
)


@_RETRY
def publish_video(
    settings,
    video_url: str,
    caption: str,
    privacy_level: str = "PUBLIC_TO_EVERYONE",
) -> tuple[str, str]:
    """Publish a video to TikTok via Content Posting API.

    Uses PULL_FROM_URL — TikTok downloads the video from the provided URL.
    The video must be publicly accessible (e.g. R2 public URL).

    Args:
        settings: App settings (needs tiktok_access_token)
        video_url: Public URL to the MP4 video
        caption: Video title/caption (max 150 chars for TikTok)
        privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY

    Returns:
        Tuple of (video_id, share_url)

    Raises:
        TikTokError: If TikTok is not configured or the API call fails
    """
    if not getattr(settings, "tiktok_access_token", ""):
        raise TikTokError("TikTok not configured — set tiktok_access_token")

    title = caption[:150]  # TikTok title limit

    with httpx.Client(timeout=120) as c:
        # Step 1: Initialize upload with PULL_FROM_URL
        r = c.post(
            f"{TIKTOK_API_BASE}/post/publish/video/init/",
            headers={
                "Authorization": f"Bearer {settings.tiktok_access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json={
                "post_info": {
                    "title": title,
                    "privacy_level": privacy_level,
                },
                "source_info": {
                    "source": "PULL_FROM_URL",
                    "video_url": video_url,
                },
            },
        )

        if r.status_code != 200:
            log.error("[tiktok] init failed: %d %s", r.status_code, r.text[:300])
            raise TikTokError(f"TikTok init failed: HTTP {r.status_code}")

        data = r.json()
        if data.get("error", {}).get("code"):
            err = data["error"]
            log.error("[tiktok] API error: %s — %s", err.get("code"), err.get("message"))
            raise TikTokError(f"TikTok API error: {err.get('message', 'unknown')}")

        publish_data = data.get("data", {})
        video_id = str(
            publish_data.get("video", {}).get("video_id")
            or publish_data.get("publish_id", "")
        )
        share_url = publish_data.get("share_url") or (
            f"https://www.tiktok.com/@unknown/video/{video_id}"
        )

        log.info("[tiktok] video published -> %s", video_id)
        return video_id, share_url


def check_tiktok_auth(settings) -> bool:
    """Check if TikTok credentials are configured."""
    return bool(getattr(settings, "tiktok_access_token", ""))