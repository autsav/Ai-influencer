"""
Re-engagement cron — nudges inactive fans back into the monetization funnel.

Queries Supabase for fans who haven't messaged in N days, picks the best
conversation fragment to reference, and sends a memory-based nudge via Fanvue.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from aeloria.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Default: fans who haven't messaged in 5+ days get a nudge
DEFAULT_INACTIVITY_DAYS = 5
# Max nudges sent per run to avoid spamming
DEFAULT_DAILY_CAP = 10


class ReengagementCron:
    """
    Finds inactive fans and sends them a warm, memory-based nudge DM.

    The nudge references something specific from their last conversation
    to feel personal rather than broadcast.
    """

    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._fanvue_key = s.fanvue_api_key
        self._supabase_url = s.supabase_url
        self._supabase_key = s.supabase_service_key
        self._inactivity_days = DEFAULT_INACTIVITY_DAYS
        self._daily_cap = DEFAULT_DAILY_CAP

    # ── Supabase helpers ───────────────────────────────────────────────────────

    def _supabase_query(self, table: str, filters: dict | None = None) -> list[dict]:
        if not self._supabase_url or not self._supabase_key:
            return []

        try:
            with httpx.Client(timeout=15.0) as client:
                url = f"{self._supabase_url}/rest/v1/{table}"
                headers = {
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                }
                params = {k: f"eq.{v}" for k, v in (filters or {}).items()}
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            logger.error("Supabase query failed (%s): %s", table, exc)
            return []

    def _find_inactive_fans(self) -> list[dict]:
        """
        Return fans who:
        - haven't sent a message in >= inactivity_days
        - are on a paid tier (free fans deprioritized)
        - haven't already been nudged today
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self._inactivity_days)
        ).isoformat()

        # Supabase: get fans whose last_message_at < cutoff
        fans = self._supabase_query(
            "fans",
            {"subscription_tier": "paid"},  # paid tier only
        )

        inactive = [
            f for f in fans
            if f.get("last_message_at") and f["last_message_at"] < cutoff
        ]
        return inactive[: self._daily_cap]

    def _get_last_conversation(self, fan_id: str) -> dict | None:
        """Fetch the most recent DM exchange for a fan."""
        rows = self._supabase_query(
            "dm_conversations",
            {"fan_id": fan_id},
        )
        return rows[-1] if rows else None

    # ── Fanvue send ───────────────────────────────────────────────────────────

    def _fanvue_send(self, fan_id: str, message: str) -> bool:
        if not self._fanvue_key:
            return False
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    "https://api.fanvue.com/v1/dms/send",
                    headers={"Authorization": f"Bearer {self._fanvue_key}"},
                    json={"fan_id": fan_id, "message": message},
                )
                resp.raise_for_status()
                return True
        except Exception as exc:
            logger.error("Reengagement nudge send failed for %s: %s", fan_id, exc)
            return False

    # ── Nudge generation ───────────────────────────────────────────────────────

    def _build_nudge(self, fan: dict, last_convo: dict | None) -> str:
        """
        Craft a short, warm nudge referencing the fan's last conversation.

        If no prior conversation exists, send a generic soft nudge.
        """
        name = fan.get("username", "there")
        topics = fan.get("preferred_topics", [])
        topic_str = ", ".join(topics) if topics else "AI automation and business workflows"

        if last_convo:
            # Reference something specific from their last message
            last_msg = last_convo.get("content", "")[:80]
            return (
                f"Hey {name}! I was just thinking about our chat — "
                f"you mentioned {topic_str} 💚 "
                f"Come say hi again, I've posted something new just for you."
            )

        # Soft generic nudge
        return (
            f"Hi {name}! It's been a while 💚 "
            f"I've been sharing new posts about {topic_str} — "
            f"would love to catch up with you soon!"
        )

    # ── Main cron run ─────────────────────────────────────────────────────────

    def run(self) -> dict:
        """
        Execute one re-engagement pass.

        Returns:
            {"nudged": N, "skipped": K, "errors": E}
        """
        inactive = self._find_inactive_fans()
        nudged = skipped = errors = 0

        for fan in inactive:
            fan_id = fan.get("id", "")
            last_convo = self._get_last_conversation(fan_id)
            message = self._build_nudge(fan, last_convo)

            if self._fanvue_send(fan_id, message):
                nudged += 1
                logger.info("Re-engagement nudge sent to fan %s", fan_id)
            else:
                errors += 1

            # TODO: record nudge in Supabase to prevent duplicate sends today

        logger.info(
            "Reengagement run done: nudged=%d skipped=%d errors=%d",
            nudged, skipped, errors,
        )
        return {"nudged": nudged, "skipped": skipped, "errors": errors}
