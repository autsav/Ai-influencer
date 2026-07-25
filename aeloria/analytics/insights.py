"""IG insights adapter — fetch per-post metrics from Meta Graph and normalize to
our `metrics` columns. $0 (insights are free). Token from token_store.
Retry: 429/5xx/network (never 400 — policy errors surface immediately)."""
import logging

import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception,
)

from aeloria.auth import token_store

log = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class InsightsError(Exception):
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
        log.error("[insights] HTTP %s: %s", r.status_code, r.text[:300])
        raise


def _value(payload: dict, name: str, default=None):
    for entry in payload.get("data", []):
        if entry.get("name") == name:
            vals = entry.get("values") or []
            if vals:
                return vals[0].get("value")
    return default


def _reach_not_followed(payload: dict):
    # Live-verified 2026-07-20 on Graph v23.0: no breakdown is compatible with
    # our media-level metrics ("follower_type" invalid; "follow_type" rejected
    # as incompatible with reach/views), so non_follower_reach is unobtainable
    # per-media. Kept for forward compat if Meta re-enables a breakdown.
    for entry in payload.get("data", []):
        if entry.get("name") == "reach":
            vals = entry.get("values") or []
            if vals:
                v = vals[0].get("value")
                if isinstance(v, dict):
                    return int(v.get("not_followed") or 0)
    return None


_RETRY = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=30, min=30, max=240),
    retry=retry_if_exception(_retryable),
    retry_error_callback=lambda s: s.outcome.result(),
)


@_RETRY
def _fetch(settings, media_id: str, slot_type: str) -> dict:
    """Raw Meta insights payload. Tenacity retries 429/5xx/network; 400 (policy)
    re-raises immediately via retry_error_callback."""
    is_reel = slot_type == "reel"
    # Metric names live-verified 2026-07-20 against Graph v23.0 media insights
    # (video_views -> views, saves -> saved). No breakdown requested — v23.0
    # rejects every breakdown for these media-level metrics (see
    # _reach_not_followed).
    metric = "reach,likes,comments,shares,saved"
    if is_reel:
        metric += ",views,ig_reels_avg_watch_time"
    params = {"metric": metric, "access_token": token_store.get()}

    with httpx.Client(timeout=60) as client:
        r = client.get(f"{settings.graph_base}/{media_id}/insights", params=params)
        _raise(r)
        return r.json()


def fetch_insights(settings, media_id: str, slot_type: str) -> dict:
    """Return normalized metrics dict for an IG media id. Reel adds views +
    avg watch time; image requests the base metric set. non_follower_reach is
    always None on v23.0 (no compatible breakdown — see _reach_not_followed)."""
    try:
        payload = _fetch(settings, media_id, slot_type)
    except httpx.HTTPStatusError as e:
        raise InsightsError(f"insights HTTP {e.response.status_code}") from e

    watch_through = None
    if slot_type == "reel":
        avg_ms = _value(payload, "ig_reels_avg_watch_time")
        if avg_ms is not None and settings.kling_video_duration:
            # Graph returns avg watch time in MILLISECONDS (live-verified:
            # 5238 for a ~5.2s watch); duration config is seconds.
            watch_through = min(
                1.0, float(avg_ms) / 1000.0 / float(settings.kling_video_duration)
            )

    # Response names are Graph v23.0 ("views"/"saved"); the normalized output
    # keys stay "views"/"saves" (our metrics columns).
    views = _value(payload, "views")
    return {
        "views": int(views) if views is not None else None,
        "likes": int(_value(payload, "likes") or 0),
        "comments": int(_value(payload, "comments") or 0),
        "shares": int(_value(payload, "shares") or 0),  # 0 when absent (images)
        "sends": 0,                                      # IG has no sends metric
        "saves": int(_value(payload, "saved") or 0),
        "watch_through": watch_through,
        "non_follower_reach": _reach_not_followed(payload),  # None for images
    }