"""
Image Prompt Engineer — multi-agent pipeline agent.

Adapted from agency-agents/design-image-prompt-engineer.md for ai-influencer-v2.

Replaces the combinatorial prompt_builder.py with a clean, single-paragraph prompt
engine calibrated to pixel benchmarks (R/G ~1.10-1.13) and explicit iPhone-quality aesthetics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Literal, Optional

import yaml
from pathlib import Path


@dataclass
class ImagePrompt:
    """Single clean paragraph prompt for FAL AI image generation."""
    prompt: str
    preset_name: str
    aspect_ratio: str  # "9:16" | "1:1" | "16:9"
    avoid: list[str]
    seed_recommendation: Optional[int] = None


class ImagePromptEngineer:
    """
    Translates a content brief into a structured image generation prompt.

    Enforces:
    - 4-layer prompt structure (subject / setting / lighting / camera)
    - Warmth calibration (R/G ~1.10-1.13) via positive lighting descriptors
    - Max 4 scene elements
    - No anti-plastic litany (positive skin texture only)
    - iPhone-quality aesthetic by default
    """

    PRESETS = {
        "cafe_morning": {
            "subject": "early 20s woman, natural skin texture visible pores peach fuzz, loose messy bun, small gold hoop earrings, minimal makeup, fresh dewy complexion",
            "setting": "cozy coffee shop, white marble table, oat milk latte to the side, large window morning light",
            "lighting": "warm morning light streaming through window, slight amber cast, natural soft shadows, slightly under-exposed iPhone quality",
            "camera": "iPhone 15 photo, candid portrait, 9:16 portrait orientation, slight grain authentic moment",
        },
        "golden_hour": {
            "subject": "early 20s woman, natural skin texture with freckles, dewy complexion, loose auburn hair framing face, soft natural glow",
            "setting": "city rooftop, golden hour, warm evening sun, bokeh city lights background",
            "lighting": "golden hour warmth, amber backlight, face lit naturally, slightly under-exposed, warm neutral tones",
            "camera": "iPhone photo, no filter, candid portrait 9:16, warm tones, slight motion softness",
        },
        "work_from_anywhere": {
            "subject": "early 20s woman, natural minimal makeup, fresh skin texture, simple stud earrings, soft smile",
            "setting": "co-working desk setup, MacBook open, succulent plant, notebook open with pen",
            "lighting": "soft diffused natural light from window, neutral warm tones, clean shadows",
            "camera": "iPhone quality, overhead angle, authentic work moment, 9:16 portrait orientation",
        },
        "weekend_adventure": {
            "subject": "early 20s woman, natural glowing skin, auburn loose waves, freckles across nose, denim jacket, tote bag",
            "setting": "busy city street, morning light, urban background, dynamic environment",
            "lighting": "bright morning sun, natural contrast, slight warmth, no harsh shadows",
            "camera": "iPhone candid street photo, slight motion blur acceptable, authentic, 9:16 portrait",
        },
        "chill_evening": {
            "subject": "early 20s woman, fresh natural skin, soft genuine smile, loose comfortable clothes, relaxed posture",
            "setting": "home apartment, couch, warm lamp light, cozy throw blanket, book on lap",
            "lighting": "warm tungsten lamp light, soft shadows, cozy evening warmth, slightly dark exposure",
            "camera": "iPhone photo, authentic cozy evening vibe, 9:16 portrait, slight grain",
        },
        "founder_moment": {
            "subject": "early 20s woman, natural focused expression, fresh skin, messy bun, glasses, confident posture",
            "setting": "co-working space, laptop screen glowing, coffee cup, whiteboard with notes in background",
            "lighting": "bright office light with window side fill, neutral warm, energetic morning feel",
            "camera": "iPhone photo, candid behind-the-shoulder or side profile, 9:16, sharp subject",
        },
    }

    DEFAULT_AVOID = [
        "plastic skin", "beauty filter", "wet hyperreal sheen", "over-sharpened",
        "oversaturated amber", "mannequin", "AI generated look", "uncanny valley",
        "stock photo framing", "studio lighting",
    ]

    def __init__(self, persona_name: str = "young_energetic"):
        self.persona_name = persona_name
        self.persona = self._load_persona(persona_name)

    def _load_persona(self, name: str) -> dict:
        """Load persona YAML from aeloria/persona/<name>.yaml."""
        path = Path(__file__).resolve().parents[1] / "persona" / f"{name}.yaml"
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text()) or {}

    def build_prompt(
        self,
        scene: Optional[str] = None,
        preset: Optional[str] = None,
        aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16",
        seed: Optional[int] = None,
    ) -> ImagePrompt:
        """Build a single clean paragraph prompt."""
        if preset and preset in self.PRESETS:
            layers = self.PRESETS[preset]
            preset_name = preset
        else:
            layers = self._build_from_scene(scene or "default scene with young woman")
            preset_name = "custom"

        paragraph = self._compose_paragraph(layers)

        return ImagePrompt(
            prompt=paragraph,
            preset_name=preset_name,
            aspect_ratio=aspect_ratio,
            avoid=list(self.DEFAULT_AVOID),
            seed_recommendation=seed,
        )

    def _build_from_scene(self, scene: str) -> dict:
        """Fallback scene-to-layers when no preset matches."""
        return {
            "subject": "early 20s woman, natural skin texture, minimal makeup, relaxed expression",
            "setting": scene,
            "lighting": "warm neutral light, soft shadows, slightly under-exposed iPhone quality",
            "camera": "iPhone photo, candid portrait, 9:16 portrait orientation, authentic",
        }

    def _compose_paragraph(self, layers: dict) -> str:
        """Compose 4 layers into one clean paragraph prompt, max ~80 words."""
        parts = [
            layers["subject"],
            layers["setting"],
            layers["lighting"],
            layers["camera"],
        ]
        return ", ".join(parts)

    def rebuild_with_feedback(
        self,
        previous_prompt: ImagePrompt | dict,
        qa_failure: list[str],
    ) -> ImagePrompt:
        """Adjust prompt based on QA gate failure reasons."""
        prev = previous_prompt if isinstance(previous_prompt, dict) else asdict(previous_prompt)
        prompt = prev.get("prompt", "")

        # Common failure → fix mapping
        fixes = {
            "warmth_RG_too_high": "neutral warm light, balanced color temperature, no amber oversaturation",
            "warmth_RG_too_low": "warm amber light, cozy golden tones, soft warm color cast",
            "edge_energy_too_high": "soft focus, slight blur on edges, no harsh detail, gentle gradient",
            "scene_too_complex": "minimalist composition, single focal subject, uncluttered background",
            "face_not_natural": "natural relaxed expression, mid-conversation, not posing, candid moment",
        }

        for failure in qa_failure:
            fix = fixes.get(failure)
            if fix and fix not in prompt:
                prompt = prompt.rstrip(", ") + f", {fix}"

        return ImagePrompt(
            prompt=prompt,
            preset_name=prev.get("preset_name", "rebuilt") + "_v2",
            aspect_ratio=prev.get("aspect_ratio", "9:16"),
            avoid=prev.get("avoid", self.DEFAULT_AVOID),
            seed_recommendation=prev.get("seed_recommendation"),
        )

    def to_json(self, prompt: ImagePrompt) -> str:
        return json.dumps(asdict(prompt), indent=2)
