"""Weekly optimizer memo: a plain-English 'what worked / double down / cut'
digest from the scores, current milestone status, and operator reject-reasons.
Sent to Telegram. LLM-authored via router."""
import json
import logging

from aeloria.config import Settings, get_settings
from aeloria.llm_router import llm_generate

log = logging.getLogger(__name__)

_MILESTONES = [(50000, "50k"), (10000, "10k"), (2000, "2k")]


class MemoError(Exception):
    pass


def milestone_reached(followers: int) -> str | None:
    for threshold, label in _MILESTONES:
        if followers >= threshold:
            return label
    return None


def reject_reasons(db, limit: int = 20) -> list[str]:
    try:
        rows = db.select_all("queue")
    except Exception:
        rows = []
    out = [r["reject_reason"].strip() for r in rows
           if r.get("approval") == "rejected" and (r.get("reject_reason") or "").strip()]
    return out[:limit]


def write_memo(db, settings: Settings | None, scores: dict, tg=None) -> str:
    s = settings or get_settings()
    followers = db.current_follower_count()
    milestone = milestone_reached(followers)
    rejects = reject_reasons(db)
    system = (
        "You are the strategy optimizer for Aeloria, a virtual Instagram influencer. "
        "Write a short weekly memo (<180 words) for the operator: what worked, what to "
        "double down on, what to cut — grounded ONLY in the data given. Plain English, "
        "no preamble."
    )
    user = (
        f"{system}\n\n"
        f"Follower count: {followers} (milestone: {milestone or 'none yet'}).\\n"
        f"Per-dimension lift scores (lift>1 = above account median):\n{json.dumps(scores.get('dimensions', {}), indent=2)}\n"
        f"Posts scored: {scores.get('n_posts', 0)}.\n"
        f"Recent operator reject-reasons (negative signal): {rejects or 'none'}."
    )
    text = llm_generate(user, timeout=60).strip()
    if not text:
        raise MemoError("model returned empty memo")
    if tg:
        header = f"📊 Weekly optimizer memo (milestone: {milestone or '—'})\n\n"
        tg.send_message(header + text)
    return text