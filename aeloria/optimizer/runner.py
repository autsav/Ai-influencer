"""Nightly optimizer: score recent posts, update bounded strategy weights, and
on Sunday emit the weekly memo. Cold-start guard holds defaults until enough
posts have metrics. A memo failure never blocks the weight update."""
import logging
from datetime import datetime, timezone

from aeloria.optimizer.memo import write_memo
from aeloria.optimizer.score import score_recent
from aeloria.optimizer.weights import update_weights

log = logging.getLogger(__name__)


def run_optimizer_pending(db, settings, persona, tg=None, now=None) -> int:
    followers = db.current_follower_count()
    scores = score_recent(db, settings, followers)
    if scores.get("n_posts", 0) < settings.optimizer_min_posts:
        log.info("optimizer cold start (%s posts) — holding defaults", scores.get("n_posts", 0))
        return 0

    current = db.current_strategy_weights()
    new_weights = update_weights(scores, current, settings.optimizer_max_weight_delta)
    db.save_strategy_weights(new_weights, note=f"n_posts={scores.get('n_posts', 0)}")

    today = now or datetime.now(timezone.utc).date()
    if today.weekday() == 6:  # Sunday
        try:
            write_memo(db, settings, scores, tg=tg)
        except Exception as e:
            log.error("optimizer memo failed: %s", e)

    try:
        from aeloria.optimizer.analyst import analyze
        from aeloria.optimizer.memo import reject_reasons
        report = analyze(scores, followers, reject_reasons(db), settings)
        if report and tg:
            tg.send_message(f"\U0001f52c Growth analyst\n\n{report}")
    except Exception as e:
        log.error("optimizer analyst failed: %s", e)
    return 1
