"""Meta Graph API — sync 2-step container publishing. Reads token from token_store.
Retry: 429/5xx/network; never 400. Image (exercisable), Reel (dormant), Story (gated)."""
import logging
import os
import time

import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception,
)

from aeloria.auth import token_store

log = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


def _get_token() -> str:
    """Token resolution chain (added 2026-08-17 for IG_ACCESS_TOKEN env-var fallback).

    Tries in order:
      1. token_store (production path; initialized at startup from Supabase)
      2. IG_ACCESS_TOKEN env var (manual fallback if Supabase is unreachable)
      3. META_LONG_LIVED_TOKEN env var (legacy .env field name; same token)

    Returns the first non-empty token. Raises RuntimeError if all three are empty.
    """
    try:
        tok = token_store.get()
        if tok:
            return tok
    except RuntimeError:
        pass  # token_store not initialized — fall through to env var
    for env_name in ("IG_ACCESS_TOKEN", "META_LONG_LIVED_TOKEN"):
        env_tok = os.environ.get(env_name, "").strip()
        if env_tok:
            log.warning(f"[meta] using {env_name} env-var fallback (token_store not available)")
            return env_tok
    raise RuntimeError(
        "No Meta token available. Either:\n"
        "  1. Initialize token_store via token_store.init(token) at startup\n"
        "  2. Set IG_ACCESS_TOKEN env var in .env"
    )


def _retryable(exc) -> bool:
    # Retry transient only: network errors + 429/5xx. NEVER 400 (policy) — re-raise.
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUSES
    return False


def _raise(r: httpx.Response):
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError:
        log.error(f"[meta] HTTP {r.status_code}: {r.text[:300]}")
        raise


def _wait_finished(client, settings, container_id, max_wait=300, interval=5):
    waited = 0
    while waited < max_wait:
        r = client.get(
            f"{settings.graph_base}/{container_id}",
            params={"fields": "status_code,status", "access_token": _get_token()},
        )
        _raise(r)
        data = r.json()
        code = data.get("status_code", "")
        if code == "FINISHED":
            return
        if code == "ERROR":
            raise RuntimeError(f"Container {container_id} error: {data.get('status')}")
        time.sleep(interval)
        waited += interval
    raise TimeoutError(f"Container {container_id} not FINISHED after {max_wait}s")


def _publish_container(client, settings, container_id):
    r = client.post(
        f"{settings.graph_base}/{settings.ig_user_id}/media_publish",
        data={"creation_id": container_id, "access_token": _get_token()},
    )
    _raise(r)
    return r.json()["id"]


_META_RETRY = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=30, min=30, max=240),
    retry=retry_if_exception(_retryable),
    retry_error_callback=lambda s: s.outcome.result(),
)


@_META_RETRY
def publish_image(settings, image_url: str, caption: str) -> tuple[str, str]:
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{settings.graph_base}/{settings.ig_user_id}/media", data={
            "image_url": image_url, "caption": caption, "access_token": _get_token(),
        })
        _raise(r)
        cid = r.json()["id"]
        _wait_finished(c, settings, cid)
        mid = _publish_container(c, settings, cid)
    log.info(f"[meta] image published -> {mid}")
    return cid, mid


@_META_RETRY
def publish_reel(settings, video_url: str, caption: str, thumb_offset_ms: int = 0) -> tuple[str, str]:
    # thumb_offset picks the reel cover frame (#38). 0 = the opening frame, which is
    # the identity-locked, face-gated hero still Kling animates from — a clean,
    # face-forward cover instead of IG's arbitrary (often mid-motion) default.
    with httpx.Client(timeout=120) as c:
        r = c.post(f"{settings.graph_base}/{settings.ig_user_id}/media", data={
            "media_type": "REELS", "video_url": video_url,
            "caption": caption, "thumb_offset": str(thumb_offset_ms),
            "access_token": _get_token(),
        })
        _raise(r)
        cid = r.json()["id"]
        _wait_finished(c, settings, cid, max_wait=600, interval=10)
        mid = _publish_container(c, settings, cid)
    log.info(f"[meta] reel published -> {mid}")
    return cid, mid


@_META_RETRY
def publish_story(settings, media_url: str, caption: str, is_video: bool = False) -> tuple[str, str]:
    with httpx.Client(timeout=60) as c:
        data = {"media_type": "STORY", "caption": caption, "access_token": _get_token()}
        data["video_url" if is_video else "image_url"] = media_url
        r = c.post(f"{settings.graph_base}/{settings.ig_user_id}/media", data=data)
        _raise(r)
        cid = r.json()["id"]
        _wait_finished(c, settings, cid)
        mid = _publish_container(c, settings, cid)
    log.info(f"[meta] story published -> {mid}")
    return cid, mid


@_META_RETRY
def publish_carousel(settings, image_urls: list[str], caption: str) -> tuple[str, str]:
    """Publish an IG carousel: create one child container per image, wait each
    FINISHED, create the CAROUSEL parent with children, publish the parent."""
    with httpx.Client(timeout=120) as c:
        child_ids = []
        for url in image_urls:
            r = c.post(f"{settings.graph_base}/{settings.ig_user_id}/media", data={
                "image_url": url, "is_carousel_item": "true",
                "access_token": _get_token(),
            })
            _raise(r)
            child = r.json()["id"]
            _wait_finished(c, settings, child)
            child_ids.append(child)
        r = c.post(f"{settings.graph_base}/{settings.ig_user_id}/media", data={
            "media_type": "CAROUSEL", "children": ",".join(child_ids),
            "caption": caption, "access_token": _get_token(),
        })
        _raise(r)
        parent = r.json()["id"]
        _wait_finished(c, settings, parent)
        mid = _publish_container(c, settings, parent)
    log.info(f"[meta] carousel published -> {mid} ({len(child_ids)} slides)")
    return parent, mid
