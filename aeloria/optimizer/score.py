"""Score recent posts vs a rolling baseline, per strategy dimension. Joins
metrics -> posts -> briefs; lift = group median / overall median. Pure db-in."""
from datetime import datetime, timedelta, timezone

_DIMENSIONS = ("content_format", "cta_kind", "series",
               "activity_category", "style_hint", "story_thread", "emotional_beat")


def tier_weights(followers: int, tiers: list) -> dict:
    chosen = tiers[0]["weights"]
    for t in tiers:
        if followers >= t["min_followers"]:
            chosen = t["weights"]
    return chosen


def engagement_score(metric: dict, weights: dict) -> int:
    return sum(int(weights.get(k, 0)) * int(metric.get(k) or 0) for k in weights)


def median(values) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    if n % 2:
        return float(s[n // 2])
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def score_recent(db, settings, followers: int = 0) -> dict:
    weights = tier_weights(followers, settings.optimizer_north_star_tiers)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=settings.optimizer_baseline_days)).isoformat()
    posts = db.select_posts_published_since(cutoff)
    briefs = {b["id"]: b for b in db.select_all("briefs")}
    eligible = [p for p in posts if p.get("platform_post_id") != "dry_run" and p.get("brief_id")]

    latest_by_post = {}
    if eligible:
        metrics = db.select_metrics_for_posts([p["id"] for p in eligible])
        for m in metrics:
            pid = m.get("post_id")
            cur = latest_by_post.get(pid)
            if cur is None or (m.get("captured_at") or "") > (cur.get("captured_at") or ""):
                latest_by_post[pid] = m

    scored = []  # (brief, score)
    for p in eligible:
        m = latest_by_post.get(p["id"])
        if not m:
            continue
        b = briefs.get(p["brief_id"])
        if not b:
            continue
        scored.append((b, engagement_score(m, weights)))

    n = len(scored)
    if n == 0:
        return {"n_posts": 0, "overall_median": 0.0, "dimensions": {}}

    overall = median([s for _, s in scored]) or 1.0
    dims = {}
    for dim in _DIMENSIONS:
        groups = {}
        for b, s in scored:
            key = b.get(dim)
            if key is None:
                continue
            groups.setdefault(key, []).append(s)
        dims[dim] = {
            k: {"lift": median(v) / overall, "n": len(v)} for k, v in groups.items()
        }
    return {"n_posts": n, "overall_median": overall, "dimensions": dims}
