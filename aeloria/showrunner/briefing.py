"""Optional Haiku briefing enrichment: turns a deterministic activity scene + the
active storyline beat into a richer, emotionally-textured prompt_seed + caption
brief + caption angle. Gated by settings.briefing_enabled; degrades to passthrough
on disable / missing key / any LLM error (never breaks the showrunner)."""
import json

import anthropic

BRIEFING_MODEL = "claude-haiku-4-5-20251001"

DAILY_BRIEFING_PROMPT = (
    "You are Aeloria's showrunner. Given her voice, today's activity scene, and the active "
    "storyline beat + emotion, write today's brief as JSON with keys: "
    "SCENE_SEED (vivid image direction: the activity with an emotional undercurrent + a real "
    "fleeting moment, never a pose), EMOTIONAL_BEAT (the one feeling), NARRATIVE_NOTE (the "
    "micro-anecdote this post advances, continuity with the storyline), CAPTION_ANGLE (the "
    "story/insight the caption should tell). One emotion, not five; never generic; "
    "contradictions welcome (her ambition vs her slowness)."
)


def enrich_brief(scene, caption_brief, emotional_beat, narrative_note, persona, settings):
    """Return (prompt_seed, caption_brief, caption_angle). Passthrough when disabled/no key/error."""
    if not getattr(settings, "briefing_enabled", False) or not getattr(settings, "anthropic_api_key", ""):
        return scene, caption_brief, narrative_note
    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        user = (f"Voice POV: {persona.wedge.voice_pov}\nActivity scene: {scene}\n"
                f"Storyline beat: {narrative_note}\nEmotion: {emotional_beat}\n"
                "Return ONLY the JSON object.")
        msg = client.messages.create(model=BRIEFING_MODEL, max_tokens=400,
                                     system=DAILY_BRIEFING_PROMPT,
                                     messages=[{"role": "user", "content": user}])
        data = json.loads(msg.content[0].text)
        return (data.get("scene_seed") or data.get("SCENE_SEED") or scene,
                data.get("caption_brief") or data.get("NARRATIVE_NOTE") or caption_brief,
                data.get("caption_angle") or data.get("CAPTION_ANGLE") or narrative_note)
    except Exception:
        return scene, caption_brief, narrative_note
