"""Claude growth-analyst: reads the nightly scored dimensions + follower tier + reject
reasons and produces an insight report with BOUNDED, human-reviewed weight nudges. Gated
by settings.optimizer_analyst_enabled; returns "" on disable / no key / any error so the
deterministic memo always stands. Never auto-applies weights."""
import json

import anthropic

ANALYST_MODEL = "claude-haiku-4-5-20251001"

DATA_ANALYZER_PROMPT = (
    "You are Aeloria's growth analyst. Given nightly post-level lift scores per dimension "
    "(content_format, cta_kind, series, activity_category, style_hint, story_thread, "
    "emotional_beat), the current follower count, and operator reject-reasons, output five "
    "short sections:\n"
    "TOP DRIVERS — dimensions/values most correlated with the tier north-star (effect size + a "
    "small-n caveat).\nUNDERPERFORMERS — what to cut and the likely why.\nAUDIENCE READ — what "
    "the reject-reasons + spread suggest about who resonates and wants more.\nEXPERIMENTS — 3 "
    "specific testable changes for next cycle.\nWEIGHT NUDGES — bounded format/CTA/style "
    "adjustments for HUMAN review.\nRules: correlation is not causation; flag low-sample "
    "findings loudly; tie every recommendation to the current tier's north-star."
)


def analyze(scores: dict, followers: int, reject_reasons: list, settings) -> str:
    if not getattr(settings, "optimizer_analyst_enabled", False) or not getattr(settings, "anthropic_api_key", ""):
        return ""
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        user = (f"Followers: {followers}\nn_posts: {scores.get('n_posts', 0)}\n"
                f"Dimensions (lift/n): {json.dumps(scores.get('dimensions', {}))}\n"
                f"Reject reasons: {reject_reasons}")
        msg = client.messages.create(model=ANALYST_MODEL, max_tokens=700,
                                     system=DATA_ANALYZER_PROMPT,
                                     messages=[{"role": "user", "content": user}])
        return msg.content[0].text.strip()
    except Exception:
        return ""
