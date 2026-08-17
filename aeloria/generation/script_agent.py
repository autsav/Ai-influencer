"""
Script Agent — multi-agent pipeline agent.

Adapted from agency-agents/marketing-video-optimization-specialist.md.

Produces 15-30s Reels scripts with:
  - 0-3s hook (one of 3 viral patterns)
  - Pattern interrupts every 7-10s
  - CTA at 80% mark

Outputs JSON consumable by Image Prompt Engineer and Caption Agent.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field, asdict
from typing import Literal


HookType = Literal["pattern_interrupt", "curiosity_gap", "relatable_pain"]


@dataclass
class ScriptBeat:
    time: str          # "0:00-0:03"
    type: str          # "hook" | "body" | "pivot" | "cta"
    text: str
    visual_direction: str
    audio: str
    pattern_interrupt: str | None = None


@dataclass
class VideoScript:
    script: list[ScriptBeat]
    trending_audio_recommendation: str
    hook_type: HookType
    retention_probability_score: float
    caption_prefix: str
    video_prompt: str  # MiniMax-H3 I2VA prompt

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# Hook templates — adapted from video-optimization-specialist + content-creator
HOOK_TEMPLATES = {
    "pattern_interrupt": [
        "She opened her laptop at 6am but wasn't working",
        "Everyone in the cafe ordered coffee. She ordered water.",
        "She deleted 3 apps before breakfast — here's why",
        "She turned her phone off for an entire day",
        "Everyone said 'follow your passion'. She did the opposite.",
        "She said no to a $50K offer. Watch what happened.",
    ],
    "curiosity_gap": [
        "I spent $0 on ads and got 10K followers — here's the actual math",
        "AI tools saved me 20 hours this week — and this is the only one that mattered",
        "There's a 3-second rule for Reels that nobody talks about",
        "Why your 'perfect' content isn't going viral",
        "I tested 14 hooks. Only 3 patterns worked.",
        "The cheapest growth hack isn't on your screen.",
    ],
    "relatable_pain": [
        "Everyone tells you to 'follow your passion' — here's what they leave out",
        "Stuck in your 9-5 and pretending you're not? Watch this",
        "If you're tired of being told to 'just post more' — this is for you",
        "Sunday scaries hit different when you actually love your job",
        "Burned out from building in public? Try this instead.",
        "When 'consistency' starts feeling like a trap",
    ],
}

AUDIO_CATEGORIES = [
    "lo-fi cafe morning loop",
    "upbeat indie pop trending",
    "minimal piano emotional",
    "trending dialogue audio",
    "phonk montage beat",
    "ambient coffee shop murmur",
]


class ScriptAgent:
    """Writes viral Reels scripts for the young_energetic persona."""

    def __init__(self, persona_name: str = "young_energetic"):
        self.persona_name = persona_name

    def write_script(
        self,
        topic: str,
        content_pillar: str = "lifestyle",
        emotional_tone: str = "energetic",
        hook_type: HookType | None = None,
        duration_sec: int = 22,
    ) -> VideoScript:
        """Generate a Reels script with hook → body → pivot → CTA structure."""

        if hook_type is None:
            chosen_hook: HookType = random.choice(list(HOOK_TEMPLATES.keys()))  # type: ignore
        else:
            chosen_hook = hook_type
        hook_type = chosen_hook
        hook_text = random.choice(HOOK_TEMPLATES[hook_type])

        # Build script beats
        beats = []

        # 0-3s: HOOK
        beats.append(ScriptBeat(
            time="0:00-0:03",
            type="hook",
            text=hook_text,
            visual_direction="extreme close-up face, eyes to camera, sudden cut-in",
            audio="music drop or silence then beat",
            pattern_interrupt="visual cut from black, sound effect trigger",
        ))

        # 3-11s: BODY (main message)
        beats.append(ScriptBeat(
            time="0:03-0:11",
            type="body",
            text=f"{topic.capitalize()} isn't what you think. Here's the real story.",
            visual_direction="medium shot, setting context, action happening",
            audio="music continues, slight energy rise",
            pattern_interrupt="camera angle change at 0:07",
        ))

        # 11-19s: BODY (evidence/proof)
        beats.append(ScriptBeat(
            time="0:11-0:19",
            type="body",
            text="I tried it for 30 days. The result changed everything.",
            visual_direction="b-roll or screen recording, quick cuts every 2s",
            audio="beat matches cuts, energy peak",
            pattern_interrupt="text overlay with bold counter-intuitive claim at 0:15",
        ))

        # 19-24s: PIVOT
        beats.append(ScriptBeat(
            time="0:19-0:24",
            type="pivot",
            text="But here's what nobody tells you.",
            visual_direction="close-up, expression change, direct eye contact",
            audio="music tension build, micro-pause",
            pattern_interrupt=None,
        ))

        # 24-end: CTA — clamp to duration
        cta_end = min(duration_sec, 30)
        beats.append(ScriptBeat(
            time=f"0:24-0:{cta_end:02d}",
            type="cta",
            text="Save this. Follow for more.",
            visual_direction="subject direct to camera, slight lean forward",
            audio="music fade + final beat drop",
            pattern_interrupt=None,
        ))

        # Compose MiniMax-H3 I2VA video prompt from script
        video_prompt = self._compose_video_prompt(beats, topic)

        # Retention probability heuristic
        retention_score = self._estimate_retention(hook_type, duration_sec, content_pillar)

        # Caption prefix from hook
        caption_prefix = hook_text

        return VideoScript(
            script=beats,
            trending_audio_recommendation=random.choice(AUDIO_CATEGORIES),
            hook_type=hook_type,
            retention_probability_score=retention_score,
            caption_prefix=caption_prefix,
            video_prompt=video_prompt,
        )

    def _compose_video_prompt(self, beats: list[ScriptBeat], topic: str) -> str:
        """Build MiniMax-H3 I2VA video prompt from beat descriptions."""
        first_beat = beats[0].visual_direction
        last_beat = beats[-1].visual_direction
        return (
            f"I2VA animation from first frame showing {first_beat}, "
            f"through continuous motion matching the topic '{topic}', "
            f"converging to a final frame with {last_beat}. "
            f"Subject speaks naturally, casual vlog aesthetic, "
            f"candid iPhone-quality video, slight handheld motion, "
            f"warm neutral lighting, 9:16 portrait orientation."
        )

    def _estimate_retention(self, hook_type: str, duration_sec: int, content_pillar: str) -> float:
        """Heuristic retention probability score (0.0-1.0)."""
        score = 0.6  # baseline
        # Hook type weight
        hook_weights = {
            "pattern_interrupt": 0.78,
            "curiosity_gap": 0.82,
            "relatable_pain": 0.85,
        }
        score = hook_weights.get(hook_type, 0.6)
        # Duration sweet spot
        if 15 <= duration_sec <= 22:
            score += 0.10
        elif duration_sec <= 30:
            score += 0.05
        else:
            score -= 0.10
        # Pillar bonuses
        if content_pillar in ["AI tools + productivity", "Founder journey"]:
            score += 0.05
        return min(score, 1.0)

    def to_json(self, script: VideoScript) -> str:
        return json.dumps(script.to_dict(), indent=2)
