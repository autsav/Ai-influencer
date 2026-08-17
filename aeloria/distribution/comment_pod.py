"""
Comment-pod orchestrator — fires controlled-engagement comments from persona
accounts within 5–10 min of post publish. NOT a bot farm — uses real IG accounts
that follow Aeloria. TOS-safe when configured per platform limits.

Pipeline:
1. Read COMMENT_POD_ACCOUNTS env (comma-separated persona account IDs).
2. load_config() resolves each ID to (ig_user_id, access_token, persona_name)
   from the Supabase platform_credentials table (same auth pattern as meta.py).
3. pick_templates() rotates through question / agreement / save_claim / follow_up
   styles, parameterized by {pillar}, {hook_type}, {topic}, {niche}, {metric}.
4. fire_async() / fire() posts one comment per configured persona account via
   the IG Graph API: POST https://graph.facebook.com/v23.0/{ig-media-id}/comments
   with staggered delays (60–600 s). Failures are logged, never raised — the
   publish loop must not be blocked by a downstream engagement-system blip.
"""
import logging
import os
import random
import asyncio
from dataclasses import dataclass
from typing import Optional

import httpx

log = logging.getLogger(__name__)

COMMENT_POD_ACCOUNTS_ENV = "COMMENT_POD_ACCOUNTS"  # comma-separated persona account IDs
DELAY_MIN_SECONDS = 60  # stagger minimum (1 min)
DELAY_MAX_SECONDS = 600  # 10 min max
GRAPH_BASE = "https://graph.facebook.com/v23.0"
DEFAULT_COMMENT_COUNT = 3


_COMMENT_TEMPLATES = {
    "question": [
        "this is huge, how did you set up {topic}?",
        "wait — does this work for {niche}?",
        "where do you even start with this?",
    ],
    "agreement": [
        "exactly this. saved.",
        "the {metric} stat alone 🤯",
        "needed to hear this today.",
    ],
    "save_claim": [
        "saving this immediately",
        "sending to my {niche} partner",
        "bookmarking for the weekend.",
    ],
    "follow_up": [
        "what's the tool called?",
        "is the prompt public?",
        "link to the workflow?",
    ],
}


@dataclass
class PodAccount:
    ig_user_id: str
    access_token: str
    persona_name: str


@dataclass
class PodConfig:
    enabled: bool
    accounts: list[PodAccount]
    comment_count: int  # how many comments per post (default 3)
    delay_seconds_min: int
    delay_seconds_max: int


def load_config(db) -> PodConfig:
    """Read COMMENT_POD_ACCOUNTS env + Supabase credentials table.

    Disabled when env is empty/missing OR when no rows resolve. Returns a
    PodConfig with accounts=[] in those cases so callers can skip cleanly.
    """
    raw = os.environ.get(COMMENT_POD_ACCOUNTS_ENV, "").strip()
    if not raw:
        log.info("comment_pod disabled: %s env empty", COMMENT_POD_ACCOUNTS_ENV)
        return PodConfig(enabled=False, accounts=[], comment_count=DEFAULT_COMMENT_COUNT,
                         delay_seconds_min=DELAY_MIN_SECONDS, delay_seconds_max=DELAY_MAX_SECONDS)

    ids = [s.strip() for s in raw.split(",") if s.strip()]
    accounts: list[PodAccount] = []
    for account_id in ids:
        try:
            rows = db.select("platform_credentials", {"account_id": account_id}, limit=1)
        except Exception as e:  # noqa: BLE001
            log.warning("comment_pod: credentials lookup failed for %s: %s", account_id, e)
            continue
        if not rows:
            log.warning("comment_pod: no platform_credentials row for account_id=%s", account_id)
            continue
        row = rows[0]
        ig_uid = row.get("ig_user_id") or ""
        token = row.get("access_token") or ""
        name = row.get("persona_name") or account_id
        if not ig_uid or not token:
            log.warning("comment_pod: account_id=%s missing ig_user_id/access_token", account_id)
            continue
        accounts.append(PodAccount(ig_user_id=ig_uid, access_token=token, persona_name=name))

    enabled = len(accounts) > 0
    if not enabled:
        log.info("comment_pod: %s env set but zero resolvable accounts", COMMENT_POD_ACCOUNTS_ENV)

    count = min(DEFAULT_COMMENT_COUNT, len(accounts)) if accounts else DEFAULT_COMMENT_COUNT
    return PodConfig(
        enabled=enabled,
        accounts=accounts,
        comment_count=count,
        delay_seconds_min=DELAY_MIN_SECONDS,
        delay_seconds_max=DELAY_MAX_SECONDS,
    )


def pick_templates(pillar: str, hook_type: str, count: int) -> list[str]:
    """Rotate through comment styles, parameterized by pillar/hook.

    Returns `count` distinct styles when possible (4 styles max). Falls back to
    random-with-replacement when count > 4. Tokens {topic}/{niche}/{metric}
    are filled from pillar/hook_type so the same template yields different
    concrete comments per post.
    """
    styles = list(_COMMENT_TEMPLATES.keys())
    chosen: list[str] = []
    rng = random.Random(f"{pillar}|{hook_type}|{count}")
    for i in range(count):
        style = styles[i % len(styles)] if i < len(styles) else rng.choice(styles)
        tmpl = rng.choice(_COMMENT_TEMPLATES[style])
        chosen.append(_fill_tokens(tmpl, pillar=pillar, hook_type=hook_type))
    return chosen


def _fill_tokens(tmpl: str, pillar: str, hook_type: str) -> str:
    """Substitute {topic}/{niche}/{metric} tokens from pillar/hook_type.

    Falls back to readable defaults so the final comment is never a raw
    template string with curly-brace placeholders.
    """
    topic = pillar.strip() or "this"
    niche_map = {
        "business_automation": "small business",
        "ai_workflows": "ops team",
        "ai_tools": "creator",
        "case_studies": "agency",
        "future_of_business": "founder",
    }
    metric_map = {
        "curiosity_gap": "6-hour",
        "shock_stat": "73%",
        "listicle": "10-step",
        "myth_bust": "industry",
        "personal_story": "12-week",
    }
    niche = niche_map.get(pillar.strip(), "creator")
    metric = metric_map.get(hook_type.strip(), "weekly")
    return (tmpl
            .replace("{topic}", topic)
            .replace("{niche}", niche)
            .replace("{metric}", metric))


async def _post_comment(client: httpx.AsyncClient, account: PodAccount,
                        post_id: str, message: str) -> bool:
    """Fire one comment. Returns True on success, False on any failure."""
    url = f"{GRAPH_BASE}/{post_id}/comments"
    try:
        r = await client.post(url, data={
            "message": message,
            "access_token": account.access_token,
        })
        if r.status_code >= 400:
            log.warning("comment_pod: %s -> HTTP %s for media %s",
                        account.persona_name, r.status_code, post_id)
            return False
        return True
    except (httpx.HTTPError, Exception) as e:  # noqa: BLE001
        log.warning("comment_pod: %s failed for %s: %s",
                    account.persona_name, post_id, e)
        return False


async def fire_async(post_id: str, pillar: str, hook_type: str,
                     config: PodConfig) -> int:
    """Async: fire N comments staggered across configured accounts.

    Returns count of comments successfully posted. Failures are logged but
    never raised — the publish loop depends on this being non-blocking.
    """
    if not config.enabled or not config.accounts:
        return 0

    count = min(config.comment_count, len(config.accounts))
    if count <= 0:
        return 0

    templates = pick_templates(pillar, hook_type, count)
    accounts = config.accounts[:count]

    fired = 0
    async with httpx.AsyncClient(timeout=30) as client:
        for i, (acct, msg) in enumerate(zip(accounts, templates)):
            if i > 0:
                delay = random.randint(config.delay_seconds_min, config.delay_seconds_max)
                await asyncio.sleep(delay)
            if await _post_comment(client, acct, post_id, msg):
                fired += 1

    log.info("comment_pod: fired %d comments for %s (pillar=%s hook=%s)",
              fired, post_id, pillar or "?", hook_type or "?")
    return fired


def fire(post_id: str, pillar: str, hook_type: str, config: PodConfig) -> int:
    """Sync wrapper. Returns count fired. Logs failures but doesn't raise.

    Designed to be called from the publish loop — exceptions here would
    block downstream queue rows, so we swallow + log.
    """
    try:
        return asyncio.run(fire_async(post_id, pillar, hook_type, config))
    except Exception as e:  # noqa: BLE001
        log.warning("comment_pod: fire() crashed for %s: %s", post_id, e)
        return 0