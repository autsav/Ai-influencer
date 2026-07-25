"""Poll Aeloria's DM inbox, draft replies, queue for approval. Dedups by
message id (source_id)."""
import logging

from aeloria.engagement.api import fetch_dm_conversations
from aeloria.engagement.drafter import draft_reply

log = logging.getLogger(__name__)


def _seen(db, source_id: str) -> bool:
    return bool(db.select("engagements", {"source_id": source_id}))


def poll_dms(db, settings, persona) -> int:
    try:
        convos = fetch_dm_conversations(settings)
    except Exception as e:
        log.error("dm fetch failed: %s", e)
        return 0
    count = 0
    for m in convos:
        mid = m.get("message_id")
        if not mid or _seen(db, mid):
            continue
        try:
            draft = draft_reply(persona, "dm", m.get("text", ""), settings=settings)
        except Exception as e:
            log.warning("dm draft skipped for %s: %s", mid, e)
            continue
        db.insert("engagements", {
            "kind": "dm", "target": m.get("sender_id", ""), "source_id": mid,
            "draft": draft, "approval": "pending",
        })
        count += 1
    return count
