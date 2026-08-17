"""Publish approved queue rows to Instagram. Sync; runs in the ThreadPoolExecutor
like run_pending. One failure doesn't stop the round."""
import datetime
import hashlib
import logging
from datetime import timezone

import httpx

from aeloria.analytics.insights import fetch_insights, InsightsError
from aeloria.auth.token_refresh import refresh_if_needed
from aeloria.distribution import comment_pod
from aeloria.distribution.growth_hacker import GrowthHackerAgent
from aeloria.publishing import meta
from aeloria.redact import redact

log = logging.getLogger(__name__)


def _jitter_offset_minutes(queue_id: str, jitter_minutes: int) -> int:
    if jitter_minutes <= 0:
        return 0
    h = int(hashlib.md5(queue_id.encode()).hexdigest(), 16)
    return (h % (2 * jitter_minutes + 1)) - jitter_minutes


def _parse_hook_type(hook_spec: str) -> str:
    """Extract the hook-type token from `hook_spec` (e.g. 'curiosity_gap: ...').
    Returns 'unknown' when hook_spec is empty/None."""
    if not hook_spec:
        return "unknown"
    head = hook_spec.strip().split(":", 1)[0].strip()
    return head or "unknown"


def record_post_analytics(db, settings, post_id: str, brief_id, slot_type: str) -> None:
    """Fetch IG insights for the published post and record to GrowthHackerAgent.

    Non-blocking: every failure (insights fetch, growth_hacker write, missing
    brief) is logged and swallowed. Callers in the publish loop rely on this
    never raising.

    Hook type and content pillar are read from the brief so learnings.json
    groups posts by the strategy dimensions that drive future generation.
    """
    brief: dict = {}
    if brief_id:
        rows = db.select("briefs", {"id": brief_id}, limit=1)
        if rows:
            brief = rows[0]
    hook_type = _parse_hook_type(brief.get("hook_spec") or "")
    content_pillar = (brief.get("pillar") or "").strip() or "unknown"

    try:
        metrics = fetch_insights(settings, post_id, slot_type)
    except (InsightsError, httpx.HTTPError, Exception) as e:  # noqa: BLE001
        # Insights fetch failure (rate-limit / network / transient) — record
        # zeros so the post still appears in learnings, then log + continue.
        log.warning(
            "insights fetch failed for post_id=%s slot=%s: %s",
            post_id, slot_type, redact(str(e)),
        )
        metrics = {
            "views": 0, "likes": 0, "comments": 0,
            "shares": 0, "sends": 0, "saves": 0,
        }

    try:
        agent = GrowthHackerAgent()
        agent.record_analytics(
            post_id=post_id,
            hook_type=hook_type,
            content_pillar=content_pillar,
            impressions=int(metrics.get("views") or 0),
            likes=int(metrics.get("likes") or 0),
            comments=int(metrics.get("comments") or 0),
            shares=int(metrics.get("shares") or 0),
            saves=int(metrics.get("saves") or 0),
            preset="",
            hashtags=None,
            scheduled_time="",
        )
    except Exception as e:  # noqa: BLE001
        # Disk/JSON failure must not block the publish loop.
        log.warning(
            "growth_hacker.record_analytics failed for post_id=%s: %s",
            post_id, redact(str(e)),
        )

    # U4 (P1-upgrades): fire controlled comment-pod engagement. Real persona
    # accounts only — never bots. Failures are logged, never raised.
    try:
        pod_cfg = comment_pod.load_config(db)
        if pod_cfg.enabled:
            fired = comment_pod.fire(
                post_id,
                pillar=content_pillar,
                hook_type=hook_type,
                config=pod_cfg,
            )
            log.info("comment_pod fired %d comments for %s", fired, post_id)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "comment_pod failed (non-blocking) for post_id=%s: %s",
            post_id, redact(str(e)),
        )


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
            # U1 (P0-upgrades): close the feedback loop. Non-blocking —
            # record_post_analytics swallows all errors and logs them.
            record_post_analytics(
                db, settings, mid,
                brief_id=q.get("brief_id"),
                slot_type=slot_type,
            )
            count += 1
        except Exception as e:
            log.error("publish row %s failed: %s", q["id"], redact(str(e)))
            if tg:
                tg.send_message(f"⚠️ IG publish failed for {q['id']}: {redact(str(e))}")

    return count