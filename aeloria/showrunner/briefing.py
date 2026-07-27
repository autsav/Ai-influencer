"""Optional briefing enrichment: turns a deterministic activity scene + the
active storyline beat into a richer, emotionally-textured prompt_seed + caption
brief + caption angle. Gated by settings.briefing_enabled; degrades to passthrough
on disable / any LLM error (never breaks the showrunner)."""
import json

from aeloria.llm_router import llm_generate

DAILY_BRIEFING_PROMPT = (
    "You are Aeloria's showrunner. Given her voice, today's activity scene, and the active "
    "storyline beat + emotion, write today's brief as JSON with keys: "
    "SCENE_SEED (vivid image direction: the activity with an emotional undercurrent + a real "
    "fleeting moment, never a pose), EMOTIONAL_BEAT (the one feeling), NARRATIVE_NOTE (the "
    "micro-anecdote this post advances, continuity with the storyline), CAPTION_ANGLE (the "
    "story/insight the caption should tell). One emotion, not five; never generic; "
    "contradictions welcome (her ambition vs her honesty about still learning)."
)


def enrich_brief(scene, caption_brief, emotional_beat, narrative_note, persona, settings):
    """Return (prompt_seed, caption_brief, caption_angle). Passthrough when disabled/error."""
    if not getattr(settings, "briefing_enabled", False):
        return scene, caption_brief, narrative_note
    try:
        user = (f"{DAILY_BRIEFING_PROMPT}\n\n"
                f"Voice POV: {persona.wedge.voice_pov}\nActivity scene: {scene}\n"
                f"Storyline beat: {narrative_note}\nEmotion: {emotional_beat}\n"
                "Return ONLY the JSON object.")
        text = llm_generate(user, timeout=60)
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0] if "```" in text else text
        data = json.loads(text.strip())
        return (data.get("scene_seed") or data.get("SCENE_SEED") or scene,
                data.get("caption_brief") or data.get("NARRATIVE_NOTE") or caption_brief,
                data.get("caption_angle") or data.get("CAPTION_ANGLE") or narrative_note)
    except Exception:
        return scene, caption_brief, narrative_note