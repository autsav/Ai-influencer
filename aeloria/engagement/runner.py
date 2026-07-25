"""Engagement round: post approved reply/DM drafts via API, poll for new
inbound/DM/outbound items, and send one batched Telegram digest. Mirrors the
analytics runner (refresh + creds gate + per-item isolation)."""
import logging
import threading
from datetime import datetime, timezone

from aeloria.auth.token_refresh import refresh_if_needed
from aeloria.engagement.api import reply_to_comment, send_dm
from aeloria.engagement.dm import poll_dms
from aeloria.engagement.inbound import poll_inbound
from aeloria.engagement.outbound import poll_outbound

log = logging.getLogger(__name__)

_KIND_LABEL = {"reply": "💬 reply", "dm": "✉️ DM", "comment_out": "📤 outbound (paste)"}

# Serializes run_engagement_pending across the scheduler job and the manual
# /trigger/engagement endpoint, which share the same process/executor — without
# this, two concurrent runs can both post the same approved row.
_RUN_LOCK = threading.Lock()


def _post_approved(db, settings) -> int:
    posted = 0
    approved = db.select_approved_unposted_engagements()
    for e in approved:
        if e.get("posted_at"):
            continue
        kind = e.get("kind")
        try:
            if kind == "reply":
                pid = reply_to_comment(settings, e["target"], e["draft"])
            elif kind == "dm":
                pid = send_dm(settings, e["target"], e["draft"])
            else:
                continue  # comment_out is manual copy-paste
        except Exception as ex:
            log.error("engagement post failed for %s: %s", e.get("id"), ex)
            continue
        db.update("engagements", e["id"], {
            "posted_at": datetime.now(timezone.utc).isoformat(), "posted_id": pid,
        })
        posted += 1
    return posted


def _send_digest(db, tg) -> None:
    pending = db.select_undigested_pending_engagements()
    if not pending or tg is None:
        return
    lines, buttons = [], []
    for e in pending:
        label = _KIND_LABEL.get(e.get("kind"), e.get("kind"))
        tgt = e.get("target", "")
        lines.append(f"{label} → {tgt}\n  “{e.get('draft', '')}”")
        buttons.append([
            (f"✅ {e['id'][:6]}", f"engapprove:{e['id']}"),
            (f"❌ {e['id'][:6]}", f"engreject:{e['id']}"),
        ])
    tg.send_message("🗣️ Engagement drafts:\n\n" + "\n\n".join(lines), buttons=buttons)
    now = datetime.now(timezone.utc).isoformat()
    for e in pending:
        db.update("engagements", e["id"], {"digested_at": now})


def run_engagement_pending(db, settings, persona, tg=None) -> int:
    with _RUN_LOCK:
        refresh_if_needed(db, settings, tg)
        if not settings.meta_app_id or not settings.ig_user_id:
            log.info("engagement disabled — no Meta creds")
            return 0

        posted = _post_approved(db, settings)

        for poll in (poll_inbound, poll_dms, poll_outbound):
            try:
                poll(db, settings, persona)
            except Exception as e:
                log.error("engagement poll %s failed: %s", poll.__name__, e)

        # digested_at filtering naturally suppresses re-spam of already-shown
        # pending items — an idle round with nothing new simply sends nothing.
        _send_digest(db, tg)
        return posted
