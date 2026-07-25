"""Scheduled analytics job: pull IG insights per post -> `metrics` rows
(+3h / +48h / nightly, idempotent) and one daily follower snapshot. $0 (Meta
insights + followers_count are free). One failure doesn't stop the round."""
import logging
from datetime import datetime, timezone

from aeloria.analytics.followers import fetch_followers
from aeloria.analytics.insights import fetch_insights
from aeloria.auth.token_refresh import refresh_if_needed

log = logging.getLogger(__name__)

_PLUS3H_HOURS = 3
_PLUS48H_HOURS = 48
_NIGHTLY_MIN_HOURS = 24


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _slot_type_for(db, brief_id) -> str:
    if not brief_id:
        return "static"
    rows = db.select("briefs", {"id": brief_id}, limit=1)
    return rows[0].get("slot_type", "static") if rows else "static"


def run_analytics_pending(db, settings) -> int:
    refresh_if_needed(db, settings, tg=None)
    if not settings.meta_app_id or not settings.ig_user_id:
        log.info("analytics disabled — no Meta creds")
        return 0

    count = 0

    # Daily follower snapshot (idempotent per utc day).
    if not db.has_follower_snapshot_today():
        try:
            followers = fetch_followers(settings)
            db.insert("follower_snapshots", {"platform": "instagram", "followers": followers})
            count += 1
        except Exception as e:
            log.error("follower snapshot failed: %s", e)

    now = datetime.now(timezone.utc)
    # select_all: posts beyond the plain select() 100-row cap must still be
    # snapshotted (nightly applies to every published post).
    posts = db.select_all("posts", order="published_at")
    for p in posts:
        if p.get("platform_post_id") == "dry_run":
            continue  # never published — no IG media to query
        try:
            age = now - _parse_dt(p["published_at"])
        except Exception:
            continue

        due = []
        if age.total_seconds() >= _PLUS3H_HOURS * 3600 and not db.latest_metric_snapshot(p["id"], "+3h"):
            due.append("+3h")
        if age.total_seconds() >= _PLUS48H_HOURS * 3600 and not db.latest_metric_snapshot(p["id"], "+48h"):
            due.append("+48h")
        if age.total_seconds() >= _NIGHTLY_MIN_HOURS * 3600 and not db.has_nightly_today(p["id"]):
            due.append("nightly")
        if not due:
            continue

        try:
            slot_type = _slot_type_for(db, p.get("brief_id"))
            metrics = fetch_insights(settings, p["platform_post_id"], slot_type)
        except Exception as e:
            log.error("insights fetch failed for post %s: %s", p["id"], e)
            continue

        for snap in due:
            row = {"post_id": p["id"], "snapshot": snap, **metrics}
            db.insert("metrics", row)
            count += 1

    return count