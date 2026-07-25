"""IG followers adapter — total follower count from Meta Graph `/{ig_user_id}`.
$0. Token from token_store. Retry 429/5xx/network; never 400 (-> FollowersError)."""
import logging

import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception,
)

from aeloria.auth import token_store

log = logging.getLogger(__name__)

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class FollowersError(Exception):
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
        log.error("[followers] HTTP %s: %s", r.status_code, r.text[:300])
        raise


_RETRY = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=30, min=30, max=240),
    retry=retry_if_exception(_retryable),
    retry_error_callback=lambda s: s.outcome.result(),
)


@_RETRY
def _fetch(settings) -> dict:
    with httpx.Client(timeout=60) as client:
        r = client.get(
            f"{settings.graph_base}/{settings.ig_user_id}",
            params={"fields": "followers_count", "access_token": token_store.get()},
        )
        _raise(r)
        return r.json()


def fetch_followers(settings) -> int:
    try:
        data = _fetch(settings)
    except httpx.HTTPStatusError as e:
        raise FollowersError(f"followers HTTP {e.response.status_code}") from e
    return int(data.get("followers_count") or 0)