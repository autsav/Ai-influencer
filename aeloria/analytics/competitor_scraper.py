"""Competitor Instagram profile scraper — wraps Apify's instagram-profile-scraper
actor. Pure adapter; no LLM calls. Falls back to a graceful no-op when
APIFY_TOKEN is missing so the rest of the pipeline stays import-safe on dev
machines and CI.

Usage:
    from aeloria.analytics.competitor_scraper import CompetitorScraper
    scraper = CompetitorScraper(settings)
    profiles = scraper.scrape_usernames(["fit_aitana", "lilmiquela"])
"""
import logging
import os
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

APIFY_ACTOR_ID = "apify/instagram-profile-scraper"
APIFY_RUN_SYNC_URL = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/run-sync-get-dataset-items"
APIFY_TOKEN_ENV = "APIFY_TOKEN"

# Hard timeout: each Apify sync run can take 30–60s for ~10 profiles.
REQUEST_TIMEOUT_SECONDS = 120.0


@dataclass
class ScrapedProfile:
    """Raw shape returned by the scraper. Mapped to CompetitorProfile in the
    tracker layer."""

    username: str
    full_name: str = ""
    followers: int = 0
    follows_count: int = 0
    posts_count: int = 0
    is_verified: bool = False
    is_private: bool = False
    biography: str = ""


class CompetitorScraper:
    """Thin Apify wrapper. Empty token -> scrape() returns [] (no-op)."""

    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get(APIFY_TOKEN_ENV, "")

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    def scrape_usernames(self, usernames: list[str]) -> list[ScrapedProfile]:
        """Run the scraper synchronously and return parsed profiles. Returns
        [] when disabled, when no usernames are given, or on any error (errors
        are logged, never raised — this is a non-blocking best-effort step)."""
        if not self.enabled:
            log.info("CompetitorScraper disabled (no APIFY_TOKEN) — skipping")
            return []
        if not usernames:
            return []
        try:
            return self._run_apify(usernames)
        except Exception as exc:
            log.error("CompetitorScraper failed: %s", exc)
            return []

    def _run_apify(self, usernames: list[str]) -> list[ScrapedProfile]:
        """POST to Apify's run-sync-get-dataset-items endpoint. The actor
        accepts a `usernames` array; we pass it through verbatim."""
        payload = {"usernames": usernames}
        params = {"token": self._token}
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = client.post(APIFY_RUN_SYNC_URL, params=params, json=payload)
            resp.raise_for_status()
            data = resp.json()
        return [self._parse_profile(item) for item in (data or []) if self._parse_profile(item).username]

    @staticmethod
    def _parse_profile(item: dict) -> ScrapedProfile:
        """Apify's profile-scraper returns a flat-ish dict; field names have
        shifted across actor versions. Use defensive `.get()` everywhere."""
        username = (
            item.get("username")
            or item.get("userName")
            or item.get("ownerUsername")
            or ""
        )
        if username and username.startswith("@"):
            username = username[1:]
        return ScrapedProfile(
            username=username.lower(),
            full_name=item.get("fullName") or item.get("full_name") or "",
            followers=int(item.get("followersCount") or item.get("followers") or 0),
            follows_count=int(item.get("followsCount") or item.get("follows") or 0),
            posts_count=int(item.get("postsCount") or item.get("posts") or 0),
            is_verified=bool(item.get("isVerified") or item.get("verified") or False),
            is_private=bool(item.get("isPrivate") or item.get("private") or False),
            biography=item.get("biography") or item.get("bio") or "",
        )
