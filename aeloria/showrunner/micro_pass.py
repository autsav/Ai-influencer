"""Daily micro-pass (rule-based, $0). Reacts to yesterday's metrics when
present: the day's top-engagement beat is echoed into today's planned story
brief as a callback. Safe no-op when there are no story briefs today or no
yesterday metrics (Phase 5 populates metrics)."""
from datetime import timedelta

from aeloria.distribution.trends import load_active


def _engagement(metric: dict) -> int:
    return (
        (metric.get("likes") or 0)
        + (metric.get("comments") or 0)
        + (metric.get("shares") or 0)
        + (metric.get("sends") or 0)
        + (metric.get("saves") or 0)
    )


def _yesterday_winning_beat(db, today) -> str | None:
    yesterday = today - timedelta(days=1)
    y_str = str(yesterday)
    # Filtered queries: the plain select() 100-row cap would return an
    # arbitrary subset of posts/metrics once the tables grow.
    posts = db.select_posts_published_since(y_str)
    y_posts = [
        p for p in posts
        if str(p.get("published_at", ""))[:10] == y_str and p.get("brief_id")
    ]
    if not y_posts:
        return None
    metrics = db.select_metrics_for_posts([p["id"] for p in y_posts])
    scores: dict[str, int] = {}
    for m in metrics:
        post = next((p for p in y_posts if p["id"] == m.get("post_id")), None)
        if not post:
            continue
        bid = post["brief_id"]
        scores[bid] = scores.get(bid, 0) + _engagement(m)
    if not scores:
        return None
    top_bid = max(scores, key=scores.get)
    rows = db.select("briefs", {"id": top_bid})
    if not rows:
        return None
    return rows[0].get("beat")


def inject_trendjack(db, persona, today, settings) -> dict | None:
    """If a fresh curated trend exists and no trend reel is slotted within the
    next 48h, inject one discovery trend-reel brief (slot = today+1). Dedup by
    trend_ref so one fresh trend produces at most one jack."""
    active = load_active(None, db)
    if not active:
        return None
    trend = active[0]  # newest curated; single-jack per pass
    ref = trend.get("ref")
    if not ref:
        return None

    horizon = [str(today + timedelta(days=n)) for n in range(3)]  # today..+2 (48h window)
    for b in db.select_all("briefs"):
        if (b.get("content_format") == "reel"
                and str(b.get("slot_day")) in horizon
                and (b.get("distribution_plan") or {}).get("trend_ref") == ref):
            return None  # already slotted this trend within 48h

    slot_day = str(today + timedelta(days=1))
    note = trend.get("note", "") or ref
    hook = f"Trend-jack: open on {note}, match-cut to Aeloria's AI-entrepreneur take within 3s."
    row = {
        "arc_id": None, "slot_day": slot_day, "slot_type": "reel",
        "content_format": "reel", "cta_kind": "comment", "audience": "discovery",
        "beat": f"trend reel: {note}", "signature": None, "hook_spec": hook,
        "prompt_seed": f"aeloria AI-entrepreneur take on trend '{ref}'",
        "caption_brief": f"react to trending {trend.get('kind', 'audio')} '{ref}' in Aeloria's voice; invite replies",
        "platforms": ["instagram"], "engine": "fal",
        "distribution_plan": {"trend_ref": ref},
        "trend_id": trend.get("id"),   # FK to trends table (None for yaml-sourced)
        "status": "planned",
    }
    return db.insert("briefs", row)


def micro_pass(db, persona, today) -> list[dict]:
    """Echo yesterday's winning beat into today's planned story brief(s).
    Returns the updated brief rows (empty list = no-op). `persona` reserved
    for future voice-aware rewrites."""
    from aeloria.config import get_settings
    inject_trendjack(db, persona, today, get_settings())

    today_briefs = db.select("briefs", {"slot_day": str(today)})
    stories = [
        b for b in today_briefs
        if b.get("slot_type") == "story" and b.get("status") == "planned"
    ]
    if not stories:
        return []

    winning = _yesterday_winning_beat(db, today)
    if not winning:
        return []

    updated = []
    for s in stories:
        new_seed = f"{winning}, a callback to yesterday's top moment"
        db.update("briefs", s["id"], {"prompt_seed": new_seed})
        updated.append({**s, "prompt_seed": new_seed})
    return updated