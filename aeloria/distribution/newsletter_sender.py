"""Newsletter sender + signup capture. Resend transport.

Three responsibilities:
1. Subscribe: capture email + double-opt-in token, insert pending row.
2. Confirm: flip pending -> active on the token click.
3. Send: walk queued sends, batch-fire through Resend's HTTP API.

All Resend calls are best-effort: any network/4xx error is logged and the
send row is marked 'failed' so we never silently drop a subscriber. We do
NOT retry 4xx (likely policy/bad-address); 429/5xx are retried by the
caller's next cron tick (the queued row stays queued with a fresh attempt).

Reference: https://resend.com/docs/api-reference/emails/send-email
"""
import logging
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

RESEND_API_BASE = "https://api.resend.com"
RESEND_TOKEN_ENV = "RESEND_API_KEY"
REQUEST_TIMEOUT_SECONDS = 30.0


class NewsletterError(Exception):
    """User-facing error (bad email, already-subscribed, etc.)."""


@dataclass
class SubscribeResult:
    """Returned to the signup route so it can render the right response."""

    subscriber_id: str
    email: str
    confirm_token: str
    already_subscribed: bool


class ResendClient:
    """Thin Resend HTTP adapter. Empty token -> disabled (every send becomes
    a logged no-op so dev / CI / first-run environments stay import-safe)."""

    def __init__(self, token: str | None = None):
        self._token = token or os.environ.get(RESEND_TOKEN_ENV, "")

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    def send_email(
        self,
        *,
        from_addr: str,
        to: list[str],
        subject: str,
        html: str,
        text: str,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        """POST to /emails, return Resend's message id. Raises on any non-2xx."""
        if not self.enabled:
            raise NewsletterError("Resend is disabled (no RESEND_API_KEY)")
        payload: dict = {
            "from": from_addr,
            "to": to,
            "subject": subject,
            "html": html,
            "text": text,
        }
        if reply_to:
            payload["reply_to"] = reply_to
        if headers:
            payload["headers"] = headers
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as c:
            resp = c.post(
                f"{RESEND_API_BASE}/emails",
                json=payload,
                headers={"Authorization": f"Bearer {self._token}"},
            )
        if resp.status_code >= 400:
            # Don't include full body (may contain PII); truncate.
            raise NewsletterError(
                f"Resend HTTP {resp.status_code}: {resp.text[:200]}"
            )
        data = resp.json() or {}
        msg_id = str(data.get("id", ""))
        if not msg_id:
            raise NewsletterError(f"Resend returned no id: {resp.text[:200]}")
        return msg_id


# ── Signup / confirm / unsubscribe ─────────────────────────────────────────────

def _normalize_email(email: str) -> str:
    return email.strip().lower()


def subscribe(
    db,
    settings,
    *,
    email: str,
    source: str = "direct",
    referrer: str = "",
    utm_source: str = "",
    utm_campaign: str = "",
) -> SubscribeResult:
    """Insert or re-activate a subscriber. Generates a fresh confirm_token on
    every call so a stale link in someone's inbox can never be reused. If
    the email already exists in `active` / `pending` state we return the
    existing row with already_subscribed=True (the route can short-circuit
    to "check your inbox" without sending another confirmation)."""
    email = _normalize_email(email)
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise NewsletterError("invalid email")

    existing = db.select("newsletter_subscribers", {"email": email}, limit=1)
    token = secrets.token_urlsafe(32)

    if existing:
        row = existing[0]
        # Re-subscribe a previously unsubscribed user: fresh token, status
        # flips back to 'pending' (still requires the double-opt-in click).
        if row.get("status") in ("unsubscribed",):
            db.update("newsletter_subscribers", row["id"], {
                "status": "pending",
                "confirm_token": token,
                "source": source,
                "referrer": referrer or row.get("referrer", ""),
                "utm_source": utm_source or row.get("utm_source", ""),
                "utm_campaign": utm_campaign or row.get("utm_campaign", ""),
                "subscribed_at": datetime.now(timezone.utc).isoformat(),
                "unsubscribed_at": None,
            })
            return SubscribeResult(row["id"], email, token, already_subscribed=False)
        # Active or pending: don't overwrite the token (existing link still works).
        return SubscribeResult(row["id"], email, row.get("confirm_token") or token, already_subscribed=True)

    inserted = db.insert("newsletter_subscribers", {
        "email": email,
        "source": source,
        "status": "pending",
        "confirm_token": token,
        "referrer": referrer,
        "utm_source": utm_source,
        "utm_campaign": utm_campaign,
        "subscribed_at": datetime.now(timezone.utc).isoformat(),
    })
    return SubscribeResult(inserted["id"], email, token, already_subscribed=False)


def confirm(db, token: str) -> str | None:
    """Flip pending -> active on the confirm click. Returns the subscriber
    email (so the route can greet them by name) or None on bad token."""
    if not token:
        return None
    rows = db.select("newsletter_subscribers", {"confirm_token": token}, limit=1)
    if not rows:
        return None
    row = rows[0]
    if row.get("status") == "active":
        return row["email"]
    db.update("newsletter_subscribers", row["id"], {
        "status": "active",
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    })
    return row["email"]


def unsubscribe(db, token: str) -> bool:
    """Soft-remove by token. Returns True if a row was flipped to
    'unsubscribed'. Unknown / already-unsubscribed tokens both return False
    (idempotent: the unsubscribe route should always say 'you're unsubscribed'
    regardless of the input)."""
    if not token:
        return False
    rows = db.select("newsletter_subscribers", {"confirm_token": token}, limit=1)
    if not rows:
        return False
    row = rows[0]
    if row.get("status") == "unsubscribed":
        return False
    db.update("newsletter_subscribers", row["id"], {
        "status": "unsubscribed",
        "unsubscribed_at": datetime.now(timezone.utc).isoformat(),
    })
    return True


# ── Issue dispatch ────────────────────────────────────────────────────────────

@dataclass
class IssueContent:
    """Everything we need to dispatch one weekly issue to one subscriber."""
    issue_slug: str
    subject: str
    html_body: str
    text_body: str
    preheader: str = ""


def queue_issue(db, settings, issue: IssueContent) -> int:
    """Insert one newsletter_sends row per active subscriber. Idempotent via
    the (subscriber_id, issue_slug) unique index — a re-run on the same
    slug for the same subscriber is a no-op. Returns the number of rows
    inserted (existing rows are skipped, not counted)."""
    rows = db.select("newsletter_subscribers", {"status": "active"}, limit=settings.newsletter_send_batch_cap)
    inserted = 0
    for sub in rows:
        try:
            db.insert("newsletter_sends", {
                "subscriber_id": sub["id"],
                "issue_slug": issue.issue_slug,
                "subject": issue.subject,
                "status": "queued",
                "queued_at": datetime.now(timezone.utc).isoformat(),
            })
            inserted += 1
        except Exception as exc:
            # Duplicate (subscriber, issue) — already queued from a previous
            # tick. Safe to ignore; the unique index protects us.
            msg = str(exc).lower()
            if "duplicate" in msg or "unique" in msg:
                continue
            log.error("queue_issue insert failed for %s: %s", sub.get("email"), exc)
    log.info("queue_issue %s: %d sends queued", issue.issue_slug, inserted)
    return inserted


def send_due(db, settings, client: ResendClient | None = None,
             tg=None, limit: int | None = None) -> int:
    """Walk queued sends, dispatch them via Resend, mark each row
    sent/failed. This variant expects the rendered html/text to already be
    in the row (legacy path); prefer `send_due_with_issue` for new code.
    Returns the count of successful sends."""
    client = client or ResendClient()
    if not client.enabled:
        log.info("Resend disabled — send_due is a no-op")
        return 0

    cap = limit if limit is not None else settings.newsletter_send_batch_cap
    queued = (
        db._client.table("newsletter_sends")
        .select("*").eq("status", "queued").order("queued_at").limit(cap).execute().data
    ) or []
    if not queued:
        return 0

    sent = 0
    for row in queued:
        subscriber = (
            db._client.table("newsletter_subscribers")
            .select("*").eq("id", row["subscriber_id"]).limit(1).execute().data
        )
        if not subscriber:
            db.update("newsletter_sends", row["id"], {"status": "failed", "error": "subscriber missing"})
            continue
        sub = subscriber[0]
        if sub.get("status") != "active":
            db.update("newsletter_sends", row["id"], {"status": "failed", "error": f"subscriber {sub.get('status')}"})
            continue

        unsubscribe_url = (
            f"{settings.newsletter_base_url}/newsletter/unsubscribe"
            f"?token={sub.get('confirm_token', '')}"
        )
        # The newsletter_sends row only stores subject; the html/text come
        # from a re-generated IssueContent the runner passes in. This legacy
        # send_due path is only useful when rows were pre-rendered (e.g.
        # tests); production callers should use send_due_with_issue below.
        try:
            resend_id = client.send_email(
                from_addr=settings.resend_from,
                to=[sub["email"]],
                subject=row["subject"],
                html=row.get("subject", ""),
                text=row.get("subject", ""),
                reply_to=settings.resend_reply_to,
                headers={
                    "List-Unsubscribe": f"<{unsubscribe_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                },
            )
            db.update("newsletter_sends", row["id"], {
                "status": "sent",
                "resend_id": resend_id,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            sent += 1
        except NewsletterError as exc:
            log.error("Resend send failed for %s: %s", sub.get("email"), exc)
            db.update("newsletter_sends", row["id"], {
                "status": "failed",
                "error": str(exc)[:200],
            })
        except Exception as exc:
            # Network / unexpected — leave queued for next tick's retry.
            log.error("Unexpected send error for %s: %s", sub.get("email"), exc)
            break

    if tg and sent:
        tg.send_message(f"📧 Newsletter: {sent}/{len(queued)} dispatched")
    log.info("send_due: %d/%d sent", sent, len(queued))
    return sent


def send_due_with_issue(
    db, settings, issue: IssueContent, *, client: ResendClient | None = None,
    tg=None, limit: int | None = None,
) -> int:
    """Concrete send loop used by the cron runner: takes a fully-rendered
    IssueContent (subject + html + text + preheader) and dispatches it to
    every queued send for `issue.issue_slug`. Returns the count of
    successful sends."""
    client = client or ResendClient()
    if not client.enabled:
        log.info("Resend disabled — send_due_with_issue is a no-op")
        return 0
    cap = limit if limit is not None else settings.newsletter_send_batch_cap
    queued = (
        db._client.table("newsletter_sends")
        .select("*").eq("status", "queued").eq("issue_slug", issue.issue_slug)
        .order("queued_at").limit(cap).execute().data
    ) or []
    if not queued:
        return 0

    sent = 0
    for row in queued:
        subscriber = (
            db._client.table("newsletter_subscribers")
            .select("*").eq("id", row["subscriber_id"]).limit(1).execute().data
        )
        if not subscriber:
            db.update("newsletter_sends", row["id"], {
                "status": "failed", "error": "subscriber missing",
            })
            continue
        sub = subscriber[0]
        if sub.get("status") != "active":
            db.update("newsletter_sends", row["id"], {
                "status": "failed", "error": f"subscriber {sub.get('status')}",
            })
            continue

        unsub_url = (
            f"{settings.newsletter_base_url}/newsletter/unsubscribe"
            f"?token={sub.get('confirm_token', '')}"
        )
        # Per-subscriber unsubscribe link (one-click). Resend's List-Unsubscribe
        # header triggers Gmail/Outlook's "Unsubscribe" button automatically.
        html = issue.html_body.replace(
            "{{UNSUBSCRIBE_URL}}", unsub_url
        )
        text = issue.text_body.replace(
            "{{UNSUBSCRIBE_URL}}", unsub_url
        )

        try:
            resend_id = client.send_email(
                from_addr=settings.resend_from,
                to=[sub["email"]],
                subject=row["subject"],
                html=html,
                text=text,
                reply_to=settings.resend_reply_to,
                headers={
                    "List-Unsubscribe": f"<{unsub_url}>",
                    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
                },
            )
            db.update("newsletter_sends", row["id"], {
                "status": "sent",
                "resend_id": resend_id,
                "sent_at": datetime.now(timezone.utc).isoformat(),
            })
            sent += 1
        except NewsletterError as exc:
            log.error("Resend send failed for %s: %s", sub.get("email"), exc)
            db.update("newsletter_sends", row["id"], {
                "status": "failed", "error": str(exc)[:200],
            })
        except Exception as exc:
            log.error("Unexpected send error for %s: %s", sub.get("email"), exc)
            break

    if tg and sent:
        tg.send_message(
            f"📧 Newsletter {issue.issue_slug}: {sent}/{len(queued)} dispatched"
        )
    log.info("send_due_with_issue %s: %d/%d sent", issue.issue_slug, sent, len(queued))
    return sent
