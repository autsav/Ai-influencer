"""Weekly optimizer memo: a plain-English 'what worked / double down / cut'
digest from the scores, current milestone status, and operator reject-reasons.
Sent to Telegram. Claude-authored."""
import json
import logging

import anthropic

from aeloria.config import Settings, get_settings

log = logging.getLogger(__name__)

MEMO_MODEL = "claude-haiku-4-5-20251001"
_MILESTONES = [(50000, "50k"), (10000, "10k"), (2000, "2k")]


class MemoError(Exception):
    pass


def milestone_reached(followers: int) -> str | None:
    for threshold, label in _MILESTONES:
        if followers >= threshold:
            return label
    return None


def reject_reasons(db, limit: int = 20) -> list[str]:
    # Only the queue stores a reject_reason (operator caption/regen rejects);
    # engagement rejections are reasonless button taps, so no text to feed.
    try:
        rows = db.select_all("queue")
    except Exception:
        rows = []
    out = [r["reject_reason"].strip() for r in rows
           if r.get("approval") == "rejected" and (r.get("reject_reason") or "").strip()]
    return out[:limit]


def write_memo(db, settings: Settings | None, scores: dict, tg=None) -> str:
    s = settings or get_settings()
    if not s.anthropic_api_key:
        raise MemoError("ANTHROPIC_API_KEY not set")
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
        f"Follower count: {followers} (milestone: {milestone or 'none yet'}).\n"
        f"Per-dimension lift scores (lift>1 = above account median):\n{json.dumps(scores.get('dimensions', {}), indent=2)}\n"
        f"Posts scored: {scores.get('n_posts', 0)}.\n"
        f"Recent operator reject-reasons (negative signal): {rejects or 'none'}."
    )
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    msg = client.messages.create(
        model=MEMO_MODEL, max_tokens=400, system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = msg.content[0].text.strip()
    if not text:
        raise MemoError("model returned empty memo")
    if tg:
        header = f"📊 Weekly optimizer memo (milestone: {milestone or '—'})\n\n"
        tg.send_message(header + text)
    return text
