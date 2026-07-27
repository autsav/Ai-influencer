"""Draft engagement replies/DMs/outbound comments in Aeloria's voice via LLM router.
A human-claim guard blocks any draft that asserts being human (persona hard rule)."""
import re

from aeloria.config import Settings, get_settings
from aeloria.persona.loader import Persona
from aeloria.llm_router import llm_generate

_KIND_INSTRUCTIONS = {
    "reply": "Reply warmly to this comment on your post. One or two sentences, natural.",
    "dm": "Reply to this direct message. Warm, brief, human-feeling but never claiming to be human.",
    "comment_out": "Leave a genuine, specific comment on another creator's post. Never generic. One sentence.",
}

# Phrases that assert humanness — block these outright. Allows up to a few
# intervening words (e.g. "i'm a living breathing person") between the
# "i am/i'm" and the human-claim noun/phrase, without unbounded/nested
# quantifiers that could open up catastrophic backtracking.
_HUMAN_CLAIM = re.compile(
    r"\b(i am|i'm|im)\s+(?:\w+\s+){0,3}"
    r"(human|person|girl|woman|guy|man|not a bot|not an ai|"
    r"not artificial|not a robot|a living)\b",
    re.IGNORECASE,
)


class DrafterError(Exception):
    pass


def claims_human(text: str) -> bool:
    return bool(_HUMAN_CLAIM.search(text or ""))


def draft_reply(persona: Persona, kind: str, context_text: str, settings: Settings | None = None) -> str:
    s = settings or get_settings()
    instruction = _KIND_INSTRUCTIONS.get(kind, _KIND_INSTRUCTIONS["reply"])
    system = (
        f"You are Aeloria, a virtual AI entrepreneur influencer. Tone: {persona.voice.get('tone', '')}. "
        f"Point of view: {persona.wedge.voice_pov} "
        f"{instruction} "
        "You must NEVER claim to be human, a real person, or deny being AI if asked directly — "
        "deflect warmly instead. Return ONLY the message text, no quotes, no preamble."
    )
    prompt = f"{system}\n\n{context_text}"
    text = llm_generate(prompt, timeout=60).strip()
    if not text:
        raise DrafterError("model returned empty draft")
    if claims_human(text):
        raise DrafterError("draft asserted humanness — blocked")
    return text