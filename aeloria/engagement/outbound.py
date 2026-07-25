"""Draft outbound targeted comments on adjacent creators' posts. API cannot
post to others' media, so drafts are copy-paste (the digest carries the target
link). Capped per day; dedups by target media id."""
import logging

from aeloria.distribution import collabs
from aeloria.engagement.api import fetch_target_recent_media
from aeloria.engagement.drafter import draft_reply

log = logging.getLogger(__name__)


def _seen(db, source_id: str) -> bool:
    return bool(db.select("engagements", {"source_id": source_id}))


def poll_outbound(db, settings, persona) -> int:
    # persona.niches is a pydantic Niches model (.core is the free-text label).
    remaining = settings.engagement_outbound_daily_cap - db.count_engagements_today("comment_out")
    if remaining <= 0:
        return 0
    niche = getattr(persona.niches, "core", "") or ""
    targets = collabs.match(collabs.load(), niche)
    count = 0
    for t in targets:
        if count >= remaining:
            break
        handle = t.get("handle")
        if not handle:
            continue
        media = fetch_target_recent_media(settings, handle)
        if not media:
            continue
        m = media[0]
        mid = m.get("id")
        if not mid or _seen(db, mid):
            continue
        try:
            draft = draft_reply(persona, "comment_out", m.get("caption", ""), settings=settings)
        except Exception as e:
            log.warning("outbound draft skipped for %s: %s", handle, e)
            continue
        db.insert("engagements", {
            "kind": "comment_out", "target": m.get("permalink") or mid,
            "source_id": mid, "draft": draft, "approval": "pending",
        })
        count += 1
    return count
