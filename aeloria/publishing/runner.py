"""Publish approved queue rows to Instagram. Sync; runs in the ThreadPoolExecutor
like run_pending. One failure doesn't stop the round."""
import datetime
import hashlib
import logging
from datetime import timezone

import httpx

from aeloria.auth.token_refresh import refresh_if_needed
from aeloria.publishing import meta
from aeloria.redact import redact

log = logging.getLogger(__name__)


def _jitter_offset_minutes(queue_id: str, jitter_minutes: int) -> int:
    if jitter_minutes <= 0:
        return 0
    h = int(hashlib.md5(queue_id.encode()).hexdigest(), 16)
    return (h % (2 * jitter_minutes + 1)) - jitter_minutes


def _parse_dt(s: str) -> datetime.datetime:
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _publish_one(settings, slot_type, kind, asset_url, caption, content_format="reel"):
    """Return media_id, or None to skip (dormant/gated). Raises on Meta errors.
    For carousels, asset_url is a list of slide image URLs."""
    if content_format == "carousel":
        _, mid = meta.publish_carousel(settings, asset_url, caption)
        return mid
    if slot_type == "reel":
        if kind != "video":
            log.info("skip reel row: needs video asset (dormant)")
            return None
        _, mid = meta.publish_reel(settings, asset_url, caption)
        return mid
    if slot_type == "story":
        is_video = kind == "video"
        _, mid = meta.publish_story(settings, asset_url, caption, is_video=is_video)
        return mid
    _, mid = meta.publish_image(settings, asset_url, caption)
    return mid


def publish_pending(db, settings, tg) -> int:
    refresh_if_needed(db, settings, tg)
    if not settings.meta_app_id or not settings.ig_user_id:
        log.info("publishing disabled — no Meta creds")
        return 0

    rows = db.select_due_for_publish("instagram")
    now = datetime.datetime.now(timezone.utc)
    count = 0

    for q in rows:
        try:
            offset = _jitter_offset_minutes(q["id"], settings.publish_jitter_minutes)
            effective_due = _parse_dt(q["slot_time"]) + datetime.timedelta(minutes=offset)
            if now < effective_due:
                continue

            if settings.publish_dry_run:
                db.insert("posts", {
                    "queue_id": q["id"], "brief_id": q.get("brief_id"),
                    "platform": "instagram", "platform_post_id": "dry_run",
                })
                count += 1
                continue

            brief = db.select("briefs", {"id": q["brief_id"]}, limit=1)
            brief = brief[0] if brief else {}
            asset = db.select("media_assets", {"id": q["asset_id"]}, limit=1)
            if not asset:
                log.warning(f"skip {q['id']}: asset {q['asset_id']} missing")
                continue
            asset = asset[0]
            slot_type = brief.get("slot_type", "static")

            if slot_type == "story" and db.current_follower_count() < settings.min_followers_for_stories:
                log.info("skip story row: below follower threshold")
                continue

            content_format = brief.get("content_format", "reel")
            if content_format == "carousel":
                cover_created = asset.get("created_at")
                slides = db.select_all("media_assets", {"brief_id": q["brief_id"]}, order="created_at")
                slide_urls = [a["r2_url"] for a in slides
                              if a.get("kind") == "image" and a.get("r2_url")
                              and (cover_created is None or (a.get("created_at") or "") >= cover_created)]
                publish_arg = slide_urls
            else:
                publish_arg = asset["r2_url"]

            try:
                mid = _publish_one(settings, slot_type, asset["kind"], publish_arg, q["caption"],
                                    content_format=content_format)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    refresh_if_needed(db, settings, tg)
                    try:
                        mid = _publish_one(settings, slot_type, asset["kind"], publish_arg, q["caption"],
                                            content_format=content_format)
                    except httpx.HTTPStatusError as e2:
                        if e2.response.status_code == 400:
                            db.update("queue", q["id"], {
                                "approval": "skipped",
                                "reject_reason": redact(f"meta_400: {e2.response.text[:200]}"),
                            })
                            if tg:
                                tg.send_message(f"⚠️ IG publish 400 (policy) for {q['id']}")
                            continue
                        log.error("publish retry failed for %s: %s", q["id"], redact(str(e2)))
                        db.update("queue", q["id"], {
                            "approval": "skipped", "reject_reason": "meta_401: retry failed",
                        })
                        if tg:
                            tg.send_message(f"⚠️ IG publish 401 retry failed for {q['id']}")
                        continue
                elif e.response.status_code == 400:
                    db.update("queue", q["id"], {
                        "approval": "skipped",
                        "reject_reason": redact(f"meta_400: {e.response.text[:200]}"),
                    })
                    if tg:
                        tg.send_message(f"⚠️ IG publish 400 (policy) for {q['id']}")
                    continue
                else:
                    raise

            if mid is None:
                continue  # dormant/gated skip

            db.insert("posts", {
                "queue_id": q["id"], "brief_id": q.get("brief_id"),
                "platform": "instagram", "platform_post_id": mid,
            })
            count += 1
        except Exception as e:
            log.error("publish row %s failed: %s", q["id"], redact(str(e)))
            if tg:
                tg.send_message(f"⚠️ IG publish failed for {q['id']}: {redact(str(e))}")

    return count