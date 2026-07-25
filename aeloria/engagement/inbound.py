"""Poll comments on Aeloria's recent posts, draft replies, queue for approval.
Dedups by comment id (source_id). $0 read; drafts cost Claude tokens."""
import logging
from datetime import datetime, timedelta, timezone

from aeloria.engagement.api import fetch_recent_comments
from aeloria.engagement.drafter import draft_reply

log = logging.getLogger(__name__)


def _seen(db, source_id: str) -> bool:
    return bool(db.select("engagements", {"source_id": source_id}))


def _within_window(timestamp: str, cutoff: datetime) -> bool:
    """True if a Meta comment timestamp (e.g. '2026-07-20T10:00:00+0000') is at
    or after the cutoff. Unparseable/missing timestamps are treated as in-window
    (fail open — dedup still prevents re-drafting)."""
    if not timestamp:
        return True
    try:
        dt = datetime.fromisoformat(timestamp.replace("+0000", "+00:00"))
    except ValueError:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt >= cutoff


def poll_inbound(db, settings, persona) -> int:
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=settings.engagement_recent_days)
    posts = db.select_posts_published_since(cutoff_dt.isoformat())
    count = 0
    for p in posts:
        media_id = p.get("platform_post_id")
        if not media_id or media_id == "dry_run":
            continue
        try:
            comments = fetch_recent_comments(settings, media_id)
        except Exception as e:
            log.error("comment fetch failed for %s: %s", media_id, e)
            continue
        for c in comments:
            cid = c.get("id")
            if not cid or _seen(db, cid):
                continue
            # Recency cutoff avoids a first-activation burst that would draft the
            # entire back-catalogue of comments in one round.
            if not _within_window(c.get("timestamp", ""), cutoff_dt):
                continue
            try:
                draft = draft_reply(persona, "reply", c.get("text", ""), settings=settings)
            except Exception as e:
                log.warning("reply draft skipped for comment %s: %s", cid, e)
                continue
            db.insert("engagements", {
                "kind": "reply", "target": cid, "source_id": cid,
                "draft": draft, "approval": "pending",
            })
            count += 1
    return count
