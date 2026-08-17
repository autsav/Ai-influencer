"""Scheduled job: generate the weekly newsletter, queue sends for every
active subscriber, then dispatch via Resend. Idempotent via the
(subscriber_id, issue_slug) unique index, so re-running within the same
week is a no-op for already-queued subscribers.

Cadence: one shot per day. The runner itself gates to the configured
weekday + hour (default Monday 09:00 UTC) so we don't need to rely on
APScheduler's crontab-style triggers, which can drift across DST changes.
"""
import logging
from datetime import datetime, timezone

from aeloria.distribution.newsletter import generate_newsletter
from aeloria.distribution.newsletter_sender import (
    IssueContent, ResendClient, queue_issue, send_due_with_issue,
)

log = logging.getLogger(__name__)


def _issue_slug(now=None) -> str:
    """Stable per-week slug: 'YYYY-MM-DD-wNN' (NN = ISO week number)."""
    d = now or datetime.now(timezone.utc)
    iso_week = d.isocalendar()
    return f"{d.strftime('%Y-%m-%d')}-w{iso_week.week:02d}"


def _select_weekly_posts(db, settings):
    """Pick the top-N posts from the last `stats_window_days` for the digest.
    Mirrors the metrics-based ranking inside distribution/newsletter.py —
    we re-implement the SQL here so we don't have to load every post row
    into Python just to score them. Returns a list of dicts shaped like the
    NewsletterPost contract."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.stats_window_days)).isoformat()
    try:
        posts = (
            db._client.table("posts").select("id, caption, platform, published_at")
            .gte("published_at", cutoff).order("published_at", desc=True).execute().data
        )
    except Exception as exc:
        log.error("_select_weekly_posts read failed: %s", exc)
        return []

    # Hydrate with metrics: latest nightly snapshot per post.
    out = []
    for p in posts or []:
        try:
            metric = db.latest_metric_for_post(p["id"])
        except Exception:
            metric = None
        if not metric:
            continue
        out.append({
            "id": p["id"],
            "caption": p.get("caption") or "",
            "image_url": None,                 # brief → media_assets lookup would add it; skip for v1
            "platform": p.get("platform", ""),
            "reach": metric.get("views") or metric.get("reach") or 0,
            "likes": metric.get("likes", 0),
            "comments": metric.get("comments", 0),
            "shares": metric.get("shares", 0),
            "saves": metric.get("saves", 0),
            "pillar": "",                       # filled by joining brief if available
        })
    # Cap at newsletter_max_posts + 50 so the generator has headroom to
    # filter empty captions etc. without re-running the DB query.
    return out[: settings.newsletter_max_posts * 10]


def run_newsletter_pending(db, settings, persona, tg=None, now=None) -> int:
    """Day-of-week gate → generate → queue → dispatch. Returns the number
    of emails sent (0 if the gate didn't fire or Resend is disabled)."""
    now = now or datetime.now(timezone.utc)
    if now.weekday() != settings.newsletter_send_weekday:
        return 0
    if now.hour < settings.newsletter_send_hour_utc:
        return 0

    client = ResendClient()
    if not client.enabled:
        log.info("Resend disabled — newsletter run is a no-op")
        return 0

    issue_slug = _issue_slug(now)

    # ── Generate ──
    weekly_posts = _select_weekly_posts(db, settings)
    if not weekly_posts:
        log.info("No posts in the last %d days — skipping newsletter", settings.stats_window_days)
        if tg:
            tg.send_message("📭 Newsletter: no posts this week, skipping")
        return 0

    try:
        result = generate_newsletter(
            weekly_posts, persona, settings=settings,
            max_posts=settings.newsletter_max_posts,
        )
    except Exception as exc:
        log.error("generate_newsletter failed: %s", exc)
        if tg:
            tg.send_message(f"⚠️ Newsletter generation failed: {exc}")
        return 0
    if not result.subject:
        log.info("generate_newsletter returned empty subject — skipping")
        return 0

    # Append a per-subscriber unsubscribe footer placeholder. The send
    # loop replaces this token with the actual one-click URL.
    unsub_footer_html = (
        '<p style="color:#999;font-size:12px;text-align:center;margin-top:30px;">'
        'Don\'t want these? '
        f'<a href="{{{{UNSUBSCRIBE_URL}}}}" style="color:#666;">Unsubscribe</a>'
        '</p>'
    )
    unsub_footer_text = "\nUnsubscribe: {{UNSUBSCRIBE_URL}}\n"

    issue = IssueContent(
        issue_slug=issue_slug,
        subject=result.subject,
        html_body=result.html_body + unsub_footer_html,
        text_body=result.text_body + unsub_footer_text,
        preheader=result.preheader,
    )

    # ── Queue (idempotent on (subscriber_id, issue_slug)) ──
    try:
        n_queued = queue_issue(db, settings, issue)
    except Exception as exc:
        log.error("queue_issue failed: %s", exc)
        if tg:
            tg.send_message(f"⚠️ Newsletter queue failed: {exc}")
        return 0

    # ── Dispatch ──
    try:
        n_sent = send_due_with_issue(db, settings, issue, client=client, tg=tg)
    except Exception as exc:
        log.error("send_due_with_issue failed: %s", exc)
        if tg:
            tg.send_message(f"⚠️ Newsletter dispatch failed: {exc}")
        return 0

    log.info(
        "Newsletter %s complete: %d queued, %d sent", issue_slug, n_queued, n_sent,
    )
    return n_sent


def has_newsletter_run_today(db) -> bool:
    """Gate: skip if a 'sent' row already exists for today's slug — protects
    against duplicate runs if the scheduler fires twice in a window."""
    slug = _issue_slug()
    try:
        rows = (
            db._client.table("newsletter_sends")
            .select("id").eq("issue_slug", slug).eq("status", "sent")
            .limit(1).execute().data
        )
        return bool(rows)
    except Exception:
        return False
