"""
Fanvue API publishing integration.

Handles post creation, PPV (Pay-Per-View) content upload, and DM interactions
via the Fanvue Creator API.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import httpx

from aeloria.config import Settings, get_settings

logger = logging.getLogger(__name__)


class PostType(Enum):
    """Fanvue content types."""

    POST = "post"                   # Free feed post
    PPV_PHOTO = "ppv_photo"        # Pay-per-view photo set
    PPV_VIDEO = "ppv_video"         # Pay-per-view video
    SUBSCRIPTION = "subscription"  # Subscription-gated post


@dataclass
class FanvuePost:
    """A Fanvue post or PPV content payload."""

    post_type: PostType
    caption: str
    media_bytes: bytes | None = None          # Raw bytes of image/video
    media_urls: list[str] | None = None        # Or pre-uploaded R2 URLs
    price: float | None = None                # PPV price in USD
    tags: list[str] | None = None
    alt_text: str | None = None


class FanvueClient:
    """
    Fanvue Creator API v1 client.

    API base: https://api.fanvue.com/v1
    Auth: Bearer token (fanvue_api_key in settings)
    """

    BASE_URL = "https://api.fanvue.com/v1"

    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._key = s.fanvue_api_key
        self._timeout = 60.0

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: Literal["GET", "POST", "DELETE"],
        path: str,
        data: dict | None = None,
        files: dict | None = None,
    ) -> dict:
        if not self._key:
            logger.warning("Fanvue %s %s skipped — no API key configured", method, path)
            return {}

        try:
            with httpx.Client(timeout=self._timeout) as client:
                url = f"{self.BASE_URL}{path}"
                if files:
                    # Multipart for media upload
                    resp = client.request(
                        method, url,
                        headers={"Authorization": f"Bearer {self._key}"},
                        data=data or {},
                        files=files,
                    )
                else:
                    resp = client.request(
                        method, url,
                        headers=self._headers(),
                        json=data,
                    )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Fanvue %s %s → HTTP %s: %s", method, path, exc.response.status_code, exc.response.text)
            raise
        except Exception as exc:
            logger.error("Fanvue %s %s failed: %s", method, path, exc)
            raise

    # ── Media upload ──────────────────────────────────────────────────────────

    def upload_media(self, file_bytes: bytes, filename: str, content_type: str) -> str:
        """
        Upload a media file to Fanvue and return the media ID.

        Returns:
            Fanvue media ID string.
        """
        result = self._request(
            "POST",
            "/media/upload",
            files={"file": (filename, file_bytes, content_type)},
        )
        if not result:
            return ""
        media_id: str = result.get("id") or result.get("media_id") or ""
        logger.info("Fanvue media uploaded: %s", media_id)
        return media_id

    # ── Post creation ──────────────────────────────────────────────────────────

    def create_post(self, post: FanvuePost) -> dict:
        """
        Publish a post or PPV content to Fanvue.

        Args:
            post: FanvuePost describing the content.

        Returns:
            API response dict including the created post ID.
        """
        payload: dict = {
            "type": post.post_type.value,
            "caption": post.caption,
        }

        # Attach media
        if post.media_bytes and post.media_urls:
            raise ValueError("Provide either media_bytes or media_urls, not both.")

        if not post.media_bytes and not post.media_urls:
            raise ValueError("media_bytes or media_urls is required to create a post.")

        if post.media_bytes:
            # Upload first
            ext = "mp4" if post.post_type in (PostType.PPV_VIDEO,) else "jpg"
            media_id = self.upload_media(
                post.media_bytes,
                f"media.{ext}",
                "video/mp4" if ext == "mp4" else "image/jpeg",
            )
            payload["media_ids"] = [media_id]
        elif post.media_urls:
            payload["media_urls"] = post.media_urls

        if post.price is not None:
            payload["price"] = post.price

        if post.tags:
            payload["tags"] = post.tags

        if post.alt_text:
            payload["alt_text"] = post.alt_text

        result = self._request("POST", "/posts", data=payload)
        post_id = result.get("id") or result.get("post_id")
        logger.info("Fanvue post created: %s (type=%s)", post_id, post.post_type.value)
        return result

    # ── PPV management ────────────────────────────────────────────────────────

    def get_ppv_sales(self, start_date: str | None = None) -> list[dict]:
        """
        Fetch PPV purchase records for the creator's content.

        Args:
            start_date: ISO date string to filter from (default: 30 days ago).
        """
        params = {}
        if start_date:
            params["from"] = start_date

        result = self._request("GET", "/ppv/sales", data=params)
        return result.get("sales", [])

    def refund_ppv(self, purchase_id: str, reason: str = "customer_request") -> dict:
        """Issue a refund for a PPV purchase."""
        return self._request(
            "POST",
            f"/ppv/{purchase_id}/refund",
            data={"reason": reason},
        )

    # ── Analytics ─────────────────────────────────────────────────────────────

    def get_insights(self, post_id: str | None = None) -> dict:
        """
        Fetch Fanvue post insights (views, likes, purchases, revenue).
        If post_id is None, returns aggregate creator insights.
        """
        path = f"/insights/{post_id}" if post_id else "/insights"
        return self._request("GET", path)
