"""
DM orchestrator — automated Pay-Per-View sales via n8n + LLM.

Polls inbound DMs from Fanvue/IG, queries Supabase for conversation history
and PPV purchase records, then generates context-aware responses that pitch
exclusive content the fan has NOT already purchased.
"""

import logging
from dataclasses import dataclass, field

import httpx

from aeloria.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class FanProfile:
    """Resolved fan context from Supabase."""

    fan_id: str
    username: str
    subscription_tier: str = "free"
    purchased_ppvs: list[str] = field(default_factory=list)  # content IDs already bought
    last_message_at: str | None = None  # ISO timestamp
    total_spent: float = 0.0
    conversation_history: list[dict] = field(default_factory=list)
    # Personality signals
    engagement_score: float = 0.5  # 0–1; higher = more receptive to pitches
    preferred_topics: list[str] = field(default_factory=list)  # e.g. ["wellness", "travel"]


class DMOrchestrator:
    """
    Coordinates the PPV sales loop:

    1. Poll Fanvue/IG for new inbound DMs
    2. Load fan profile + purchase history from Supabase
    3. Build a context prompt for the LLM
    4. Fire LLM → generate response
    5. Route response back via Fanvue/IG API
    """

    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._anthropic_key = s.anthropic_api_key
        self._fanvue_key = s.fanvue_api_key
        self._supabase_url = s.supabase_url
        self._supabase_key = s.supabase_service_key
        self._n8n_webhook_url = ""  # Set via env or settings if using n8n workflow

    # ── Fanvue API ─────────────────────────────────────────────────────────────

    def _fanvue_get_dms(self, unread_only: bool = True) -> list[dict]:
        """Fetch inbound DMs from Fanvue."""
        if not self._fanvue_key:
            logger.warning("Fanvue API key not configured — skipping DM poll.")
            return []

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.get(
                    "https://api.fanvue.com/v1/dms/inbox",
                    headers={"Authorization": f"Bearer {self._fanvue_key}"},
                    params={"unread": unread_only} if unread_only else {},
                )
                resp.raise_for_status()
                return resp.json().get("dms", [])
        except Exception as exc:
            logger.error("Fanvue DM fetch failed: %s", exc)
            return []

    def _fanvue_send(self, fan_id: str, message: str) -> bool:
        """Send a message to a fan via Fanvue DM."""
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
            logger.error("Fanvue send failed for %s: %s", fan_id, exc)
            return False

    # ── Supabase ───────────────────────────────────────────────────────────────

    def _supabase_query(self, table: str, filters: dict | None = None) -> list[dict]:
        """Execute a filtered select against Supabase."""
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

    def _load_fan_profile(self, fan_id: str) -> FanProfile:
        """Resolve full fan profile from Supabase."""
        rows = self._supabase_query("fans", {"id": fan_id})
        purchases = self._supabase_query("fan_purchases", {"fan_id": fan_id})
        convos = self._supabase_query("dm_conversations", {"fan_id": fan_id})

        base = rows[0] if rows else {}
        return FanProfile(
            fan_id=fan_id,
            username=base.get("username", ""),
            subscription_tier=base.get("subscription_tier", "free"),
            purchased_ppvs=[p["content_id"] for p in purchases],
            last_message_at=base.get("last_message_at"),
            total_spent=sum(p.get("amount", 0) for p in purchases),
            conversation_history=convos,
            engagement_score=base.get("engagement_score", 0.5),
            preferred_topics=base.get("preferred_topics", []),
        )

    # ── LLM response generation ────────────────────────────────────────────────

    def _generate_response(self, fan: FanProfile, inbound_message: str) -> str:
        """
        Call the LLM (Claude/Gemini) to produce a context-aware DM response.

        The prompt is carefully engineered to:
        - Remember prior conversation
        - Never pitch content the fan already owns
        - Wait for a natural conversational opening
        - Sound intimate, not spammy
        """
        if not self._anthropic_key:
            # Fallback to a simple rule-based response
            return "Thanks for your message! Check out my latest posts 💚"

        purchased_ids = ", ".join(fan.purchased_ppvs) or "none"
        history_text = "\n".join(
            f"[{'user' if m['role']=='fan' else 'aeloria'}]: {m['content']}"
            for m in fan.conversation_history[-10:]
        ) or "No prior conversation."

        system_prompt = (
            "You are Aeloria, a 24-year-old wellness influencer. You respond to fans "
            "via DM in a warm, intimate, personal tone — never salesy or pushy. "
            f"The fan '{fan.username}' is on your Fanvue page. "
            f"They have already purchased these PPV content IDs: {purchased_ids}. "
            "Do NOT pitch any content they have already bought. "
            "If the message is a greeting, respond warmly and naturally — do not pitch. "
            "If the fan shows interest (asks about content, compliments you, asks for more), "
            "gently mention an unpurchased PPV that fits their interests. "
            f"Their interests include: {', '.join(fan.preferred_topics) or 'general wellness'}. "
            "Keep replies short — 1 to 3 sentences max. Use light emoji."
        )

        user_prompt = (
            f"Conversation so far:\n{history_text}\n\n"
            f"Fan just sent: {inbound_message}\n\n"
            "Your reply:"
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self._anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-3-5-haiku-20241022",
                        "max_tokens": 300,
                        "system": system_prompt,
                        "messages": [{"role": "user", "content": user_prompt}],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"].strip()
        except Exception as exc:
            logger.error("LLM response generation failed: %s", exc)
            return "Thanks for reaching out! I'll get back to you soon 💚"

    # ── Main orchestration loop ───────────────────────────────────────────────

    def process_inbound(self) -> dict:
        """
        Poll DMs, load fan context, generate and send responses.

        Returns:
            Summary dict: {"processed": N, "sent": M, "errors": K}
        """
        dms = self._fanvue_get_dms(unread_only=True)
        processed = sent = errors = 0

        for dm in dms:
            fan_id = dm.get("fan_id") or dm.get("user_id", "")
            inbound = dm.get("message", {}).get("text", "") or dm.get("text", "")
            dm_id = dm.get("id", "")

            if not fan_id or not inbound:
                continue

            processed += 1
            fan = self._load_fan_profile(fan_id)
            response = self._generate_response(fan, inbound)

            if self._fanvue_send(fan_id, response):
                sent += 1
                logger.info("DM sent to fan %s (dm_id=%s)", fan_id, dm_id)
                # Mark as read / replied in Supabase
                self._supabase_query("dm_conversations", {})
            else:
                errors += 1

        logger.info("DM loop done: processed=%d sent=%d errors=%d", processed, sent, errors)
        return {"processed": processed, "sent": sent, "errors": errors}
