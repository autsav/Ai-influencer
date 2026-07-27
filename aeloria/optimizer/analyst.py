"""Growth-analyst: reads the nightly scored dimensions + follower tier + reject
reasons and produces an insight report with BOUNDED, human-reviewed weight nudges. Gated
by settings.optimizer_analyst_enabled; returns "" on disable / any error so the
deterministic memo always stands. Never auto-applies weights."""
import json

from aeloria.llm_router import llm_generate

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
    if not getattr(settings, "optimizer_analyst_enabled", False):
        return ""
    try:
        user = (f"{DATA_ANALYZER_PROMPT}\n\n"
                f"Followers: {followers}\nn_posts: {scores.get('n_posts', 0)}\n"
                f"Dimensions (lift/n): {json.dumps(scores.get('dimensions', {}))}\n"
                f"Reject reasons: {reject_reasons}")
        return llm_generate(user, timeout=60).strip()
    except Exception:
        return ""