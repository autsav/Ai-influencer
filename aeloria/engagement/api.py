"""Meta Graph adapter for engagement: read comments/DMs, post replies/DMs.
Mirrors analytics/insights.py — tenacity retry on 429/5xx/network, 400 surfaces
immediately. Token via token_store."""
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from aeloria.auth import token_store

log = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class EngagementApiError(Exception):
    pass


def _retryable(exc) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUSES
    return False


def _raise(r: httpx.Response):
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError:
        log.error("[engagement] HTTP %s: %s", r.status_code, r.text[:300])
        raise


_RETRY = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=30, min=30, max=240),
    retry=retry_if_exception(_retryable),
    retry_error_callback=lambda s: s.outcome.result(),
)


@_RETRY
def _fetch_comments_raw(settings, media_id):
    with httpx.Client(timeout=60) as c:
        r = c.get(f"{settings.graph_base}/{media_id}/comments", params={
            "fields": "id,text,username,timestamp", "access_token": token_store.get(),
        })
        _raise(r)
        return r.json()


def fetch_recent_comments(settings, media_id: str) -> list[dict]:
    try:
        payload = _fetch_comments_raw(settings, media_id)
    except httpx.HTTPStatusError as e:
        raise EngagementApiError(f"comments HTTP {e.response.status_code}") from e
    out = []
    for c in payload.get("data", []):
        out.append({
            "id": c.get("id"), "text": c.get("text", ""),
            "username": c.get("username", ""), "timestamp": c.get("timestamp", ""),
        })
    return out


@_RETRY
def reply_to_comment(settings, comment_id: str, message: str) -> str:
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{settings.graph_base}/{comment_id}/replies", data={
            "message": message, "access_token": token_store.get(),
        })
        _raise(r)
        return r.json()["id"]


@_RETRY
def _fetch_conversations_raw(settings):
    with httpx.Client(timeout=60) as c:
        r = c.get(f"{settings.graph_base}/{settings.ig_user_id}/conversations", params={
            "platform": "instagram",
            "fields": "id,messages.limit(1){id,message,from}",
            "access_token": token_store.get(),
        })
        _raise(r)
        return r.json()


def fetch_dm_conversations(settings) -> list[dict]:
    try:
        payload = _fetch_conversations_raw(settings)
    except httpx.HTTPStatusError as e:
        raise EngagementApiError(f"conversations HTTP {e.response.status_code}") from e
    out = []
    for conv in payload.get("data", []):
        msgs = (conv.get("messages") or {}).get("data") or []
        if not msgs:
            continue
        m = msgs[0]
        sender = (m.get("from") or {}).get("id", "")
        # Skip our own outbound messages (sender == our ig user id).
        if sender and sender == settings.ig_user_id:
            continue
        out.append({
            "id": conv.get("id"), "message_id": m.get("id"),
            "text": m.get("message", ""), "sender_id": sender,
        })
    return out


@_RETRY
def send_dm(settings, recipient_id: str, message: str) -> str:
    with httpx.Client(timeout=60) as c:
        r = c.post(
            f"{settings.graph_base}/{settings.ig_user_id}/messages",
            params={"access_token": token_store.get()},
            json={"recipient": {"id": recipient_id}, "message": {"text": message}},
        )
        _raise(r)
        data = r.json()
        return data.get("message_id") or data.get("id")


@_RETRY
def _fetch_discovery_raw(settings, username):
    with httpx.Client(timeout=60) as c:
        r = c.get(f"{settings.graph_base}/{settings.ig_user_id}", params={
            "fields": f"business_discovery.username({username}){{media.limit(1){{id,caption,permalink}}}}",
            "access_token": token_store.get(),
        })
        _raise(r)
        return r.json()


def fetch_target_recent_media(settings, username: str) -> list[dict]:
    """Most-recent public media for a business/creator account, via
    business_discovery. Empty list if the account is private/unreachable."""
    try:
        payload = _fetch_discovery_raw(settings, username)
    except httpx.HTTPStatusError:
        return []  # private / not discoverable — skip target, not an error
    bd = payload.get("business_discovery") or {}
    media = (bd.get("media") or {}).get("data") or []
    return [{"id": m.get("id"), "caption": m.get("caption", ""), "permalink": m.get("permalink", "")}
            for m in media]
