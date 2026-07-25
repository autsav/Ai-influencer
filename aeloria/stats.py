"""/stats readout: latest follower snapshot, milestone gates, and rolling
metric aggregates over posts published in the last `stats_window_days`.
Pure db-in function — no network calls."""
from datetime import datetime, timedelta, timezone

MILESTONES = {"wk3_2k": 2000, "wk6_10k": 10000, "wk10_50k": 50000}
_SUM_FIELDS = ("views", "likes", "comments", "shares", "sends", "saves")


def _parse_dt(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _latest_metric(db, post_id) -> dict | None:
    # Ordered limit-1 query — a plain select() caps at 100 rows and could miss
    # the newest snapshot once a post accumulates many nightly rows.
    return db.latest_metric_for_post(post_id)


def build_stats(db, settings) -> dict:
    followers = db.current_follower_count()
    milestones = {name: followers >= threshold for name, threshold in MILESTONES.items()}

    window_days = settings.stats_window_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    sums = {f: 0 for f in _SUM_FIELDS}
    non_follower_reach = 0
    watch_through = []
    n_posts = 0
    # Cutoff pushed into the query so window aggregates stay correct past the
    # plain select() 100-row cap.
    for p in db.select_posts_published_since(cutoff.isoformat()):
        published_at = p.get("published_at")
        if not published_at:
            continue
        try:
            if _parse_dt(published_at) < cutoff:
                continue
        except ValueError:
            continue
        n_posts += 1
        m = _latest_metric(db, p["id"])
        if not m:
            continue
        for f in _SUM_FIELDS:
            sums[f] += int(m.get(f) or 0)
        non_follower_reach += int(m.get("non_follower_reach") or 0)
        if m.get("watch_through") is not None:
            watch_through.append(float(m["watch_through"]))

    return {
        "followers": followers,
        "milestones": milestones,
        "metrics": {
            "window_days": window_days,
            "posts": n_posts,
            **sums,
            "watch_through_avg": (
                round(sum(watch_through) / len(watch_through), 4) if watch_through else None
            ),
            "non_follower_reach": non_follower_reach,
        },
    }
