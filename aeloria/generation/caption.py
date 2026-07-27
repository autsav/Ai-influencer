import hashlib

from aeloria.config import Settings, get_settings
from aeloria.persona.loader import Persona
from aeloria.llm_router import llm_generate

# Tasteful AI-transparency line — appended after the hashtags (disclosure #63 +
# Meta's AI-content labeling policy). Toggle via settings.caption_ai_disclosure.
AI_DISCLOSURE = "🤖 AI-generated · a virtual creator"

CTA_INSTRUCTIONS = {
    "save": "End with a natural save-prompt so people bookmark this for later (saves are weighted "
            "heavily by the algorithm) — e.g. 'save this for the day you need it'. Never spammy.",
    "share": "End by nudging them to send this to one specific person ('send this to the friend who…'). "
             "A share travels further than a like.",
    "comment": "End with ONE effortless binary or this-or-that question that invites a reply "
               "(e.g. 'team slow morning or team snooze?'). Never a generic 'thoughts?'.",
    "none": "",
}

# Viral first-line hook frameworks (2026 short-form): the caption's opening line must
# stop the scroll in ~1.5s. Rotate the angle to fit the scene.
_HOOK_FRAMEWORK = (
    "Write the FIRST LINE as a 1.5-second hook that stops the scroll: open mid-thought, "
    "no greeting or throat-clearing. Use whichever fits the scene — a curiosity gap (a premise "
    "without the payoff), a gently contrarian myth-bust, or a loss-aversion angle (what they're "
    "getting wrong or missing). Then deliver a tight micro-story or one sharp insight — no filler."
)


_CAPTION_FRAMEWORKS = [
    "a micro-story arc (setup -> turn -> quiet resonance)",
    "PAS: name a real problem, agitate the ache, resolve with her take",
    "an open loop / cliffhanger that teases the next post in the storyline",
    "a quiet confession — lead with a small vulnerability, connection over polish",
    "a gently contrarian take that reframes what people assume",
]


def _pick_by_brief(pool, brief, salt):
    key = str(brief.get("id") or brief.get("beat", ""))
    h = int(hashlib.md5(f"{key}-{salt}".encode()).hexdigest(), 16)
    return pool[h % len(pool)]


class CaptionError(Exception):
    pass


def write_caption(
    persona: Persona,
    brief: dict,
    settings: Settings | None = None,
    distribution_plan: dict | None = None,
    cta_kind: str = "none",
) -> str:
    s = settings or get_settings()

    rules = "; ".join(persona.voice.get("caption_rules", []))
    cta = CTA_INSTRUCTIONS.get(cta_kind, "")
    catchphrases = persona.voice.get("catchphrases") or ([persona.voice["catchphrase"]]
                                                         if persona.voice.get("catchphrase") else [])
    catchphrase = _pick_by_brief(catchphrases, brief, 7) if catchphrases else ""
    framework = _pick_by_brief(_CAPTION_FRAMEWORKS, brief, 3)
    system = (
        f"You write scroll-stopping Instagram captions for Aeloria, a virtual AI entrepreneur influencer. "
        f"Tone: {persona.voice.get('tone', '')}. "
        f"Point of view: {persona.wedge.voice_pov} "
        f"Rules: {rules}. "
        f"{_HOOK_FRAMEWORK} "
        f"Structure the body as {framework}. "
        + (f"Weave in Aeloria's signature line where it lands naturally: \"{catchphrase}\". " if catchphrase else "")
        + (f"Call to action: {cta} " if cta else "")
        + "Return ONLY the caption text, no quotes, no preamble."
    )
    active_trend = (distribution_plan or {}).get("active_trend")
    user = (
        f"{system}\n\n"
        f"Scene: {brief.get('beat') or brief.get('prompt_seed', '')}\n"
        f"Caption brief: {brief.get('caption_angle') or brief.get('caption_brief') or brief.get('prompt_seed', '')}\n"
        + (f"Emotion to carry (just one): {brief['emotional_beat']}\n" if brief.get("emotional_beat") else "")
        + (f"Storyline this post advances: {brief['narrative_note']}\n" if brief.get("narrative_note") else "")
        + (f"Location: {brief['location']} — localize with one specific real detail\n" if brief.get("location") else "")
        + (f"Active trend, nod to it ONLY if it fits naturally: {active_trend}\n" if active_trend else "")
    )
    text = llm_generate(user, timeout=60)
    text = text.strip()
    if not text:
        raise CaptionError("model returned empty caption")
    tags = (distribution_plan or {}).get("hashtags") or []
    if tags:
        text = f"{text}\n\n{' '.join(tags)}"
    if getattr(s, "caption_ai_disclosure", True):
        text = f"{text}\n\n{AI_DISCLOSURE}"
    return text