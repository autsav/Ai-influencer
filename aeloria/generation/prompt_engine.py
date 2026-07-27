"""
Ultra-Realistic Prompt Engine — SOUL 2 / Z Studio aesthetic.
Modular, plug-and-play framework for generating infinite hyper-realistic
AI influencer and photography prompts.

Usage:
    python -m aeloria.generation.prompt_engine --count 5 --format json
    python -m aeloria.generation.prompt_engine --count 3 --format text
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from typing import Literal


# ─────────────────────────────────────────────────────────────────────────────
# MODULE DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

from aeloria.generation.creative_database import (
    CREATIVE_CAMERA_ANGLES,
    CREATIVE_POSES,
    WARDROBE_LOCK_SUFFIX,
    HAIR_LOCK_SUFFIX,
)

MODULE_A_CAMERA = [
    # Phone
    "High-resolution front-facing smartphone selfie",
    "Wide-angle smartphone lens, slightly tilted angle creating a fisheye perspective, imperfect framing",
    # Point-and-shoot
    "Shot on Canon G7X Mark III, high-quality 4K",
    # DSLR
    "DSLR photo, 85mm lens look, shallow depth of field, ultra HD, high dynamic range",
    # Macro
    "8K resolution, hyper-realistic macro portrait photograph, extreme close-up frontal view",
]

MODULE_B_AESTHETIC = [
    "Ultra-realistic candid street portrait",
    "Colorful glam early-2000s snapshot, grainy low-res nostalgia",
    "Luxury casual street style aesthetic",
    "Clean sporty fashion aesthetic",
    "Bold fashion editorial aesthetic",
]

MODULE_C_SUBJECT = [
    {
        "descriptor": "aeloria woman, a clearly adult woman in her mid-twenties, slender build",
        "features": "auburn hair in a loose messy bun with flyaway strands framing her face, green eyes, fair skin with freckles across nose and cheeks, visible pores, peach fuzz on upper lip and forehead, gold hoop earrings catching the light",
        "poses": [
            "Hands lifted to her mouth in a playful pose",
            "Playful kissing expression while winking",
            "Relaxed confident stance, slight hip shift",
            "Asymmetric pose with one leg bent and lifted",
            "Glancing back over one shoulder with a knowing half-smile",
            "Caught mid-laugh, genuine and unposed",
            "One hand pushing hair back from her face, thoughtful gesture",
            "Leaning casually against a wall, effortlessly composed",
            "Sitting in profile, looking into the middle distance, lost in thought",
            "Mid-stride walking forward, natural unhurried motion",
        ],
    },
]

MODULE_D_WARDROBE = [
    {
        "style": "Casual/Street",
        "description": "Oversized vintage white graphic t-shirt tucked into low-rise blue jeans with a brown leather belt",
    },
    {
        "style": "Winter",
        "description": "Bright blue knitted beanie, large dark navy puffer jacket, and small oval black sunglasses",
    },
    {
        "style": "Y2K/Glam",
        "description": "Fitted crop tank top with a deep neckline and a black sequin micro mini skirt featuring lace-up side details",
    },
    {
        "style": "High Fashion",
        "description": "Black silk mini cheongsam with silver floral embroidery and a high slit",
    },
    {
        "style": "Slow Living",
        "description": "Oversized chunky-knit oatmeal sweater over fitted trousers with gold hoop earrings",
    },
    {
        "style": "Earthy Linen",
        "description": "Linen shirt tucked into high-waisted wide-leg jeans with gold hoop earrings and sandals",
    },
    {
        "style": "Forest Cozy",
        "description": "Ribbed knit top and wide-leg trousers in tonal earthy tones with a linen scarf draped loosely",
    },
    {
        "style": "Travel Chic",
        "description": "Soft suede jacket over a slip dress with worn leather boots and layered gold jewelry",
    },
    {
        "style": "Athleisure",
        "description": "Cropped cardiigan with low-slung wide-leg trousers and white sneakers",
    },
    {
        "style": "Editorial Knit",
        "description": "Body-skimming knit midi dress with delicate gold chain necklace catching the light",
    },
]

MODULE_E_LOCATION = [
    {
        "setting": "Urban",
        "description": "Busy downtown city street surrounded by tall historic buildings with fire escapes and storefront windows",
    },
    {
        "setting": "Nature/Outdoor",
        "description": "Rocky lakeshore with a large alpine lake and dramatic snow-capped mountains",
    },
    {
        "setting": "Indoor/Intimate — Minimalist",
        "description": "Minimalist indoor living space with worn floors",
    },
    {
        "setting": "Indoor/Intimate — Dark Luxury",
        "description": "Dimly lit luxury dark interior with glossy black lacquered walls and warm gold oriental patterns",
    },
    {
        "setting": "Home Office",
        "description": "A minimal home office with clean white desk, MacBook, warm desk lamp, one plant, morning light",
    },
    {
        "setting": "Mountain Retreat",
        "description": "A modern coworking space with bright white desks, plants, and other founders working",
    },
    {
        "setting": "Coastal Walk",
        "description": "A windswept coastal path with wild grass, grey waves crashing on rocks below, overcast diffused light",
    },
    {
        "setting": "Garden",
        "description": "A wild cottage garden with overgrown herbs, lavender, and a rusted wrought-iron bench in dappled shade",
    },
    {
        "setting": "London Street",
        "description": "A cobbled London street with red brick facades, a vintage streetlamp, and soft rain misting the pavement",
    },
    {
        "setting": "Café",
        "description": "A warm Parisian café with copper espresso machines, patinated wood tables, and steam rising from a cup",
    },
]

MODULE_F_LIGHTING = [
    {
        "type": "Soft/Natural",
        "description": "Soft natural window light filters from the left, casting warm highlights and gentle shadows",
    },
    {
        "type": "Flash Photography",
        "description": "Direct on-camera flash effect — crisp flash highlights, sharp micro-contrast, glossy skin reflections, realistic flash shadows",
    },
    {
        "type": "Imperfections",
        "description": "Slightly blurry and low-resolution quality, subtle compression artifacts, and grainy pixelation",
    },
    {
        "type": "Imperfections — Lens Glare",
        "description": "Natural lens glare from sunlight",
    },
]

# ── Aeloria skin realism block (anti-plastic) ──────────────────────────────────
SKIN_REALISM = (
    "Raw authentic skin with visible pores across the cheeks and nose, "
    "faint freckles, subtle natural redness around the nose, tiny skin bumps, "
    "fine peach fuzz catching the light, soft natural oil highlights on the nose "
    "and forehead, gentle under-eye warmth — no smoothing, no beauty filter. "
    "Real skin texture preserved."
)

# ── Identity lock (end line) ──────────────────────────────────────────────────
IDENTITY_LOCK = (
    "Preserve aeloria's exact identity — same face, auburn hair and the same "
    "recognizable person in every image. Do NOT change aeloria's facial features "
    "or body shape."
)

NEGATIVE_PROMPT = (
    "different person, altered identity, face swap, idealized beauty, generic face, "
    "doll face, AI face, plastic skin, over-retouched skin, smoothing, "
    "blank dull expression, stiff centered pose, airbrushed skin, waxy skin, "
    "beauty filter, CGI look, distorted anatomy, exaggerated proportions, "
    "duplicate limbs, low resolution, smooth plastic skin, porcelain skin, "
    "mannequin, doll-like, ring light, artificial rim light, oversharpened, "
    "digital noise, banding, cartoon, anime, illustration, flat lighting, "
    "softbox look, HDR look, text, logo, watermark, signature, frame, border"
)

HEX_PALETTES = [
    ["#090b11", "#d1d1c9", "#c1c1bc"],
    ["#2c1a1d", "#f5e6d3", "#c49a7c"],
    ["#0d1117", "#58a6ff", "#c9d1d9"],
    ["#1a1a2e", "#e94560", "#f5f5f5"],
    ["#f8f0e3", "#c5a880", "#8b6f47"],
]

ASPECT_RATIOS = [
    "Vertical (portrait) 4:5",
    "Square 1:1",
    "Horizontal landscape 16:9",
]


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT ENGINE
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GeneratedPrompt:
    """A single generated prompt with all its components."""
    camera: str
    aesthetic: str
    subject_descriptor: str
    subject_features: str
    subject_pose: str
    wardrobe_style: str
    wardrobe_description: str
    location_setting: str
    location_description: str
    lighting_type: str
    lighting_description: str
    imperfections: str | None
    hex_palette: list[str]
    aspect_ratio: str
    negative_prompt: str = field(default=NEGATIVE_PROMPT, repr=False)

    def build_text(self) -> str:
        """Assemble the full natural-language prompt string."""
        parts = [
            self.camera,
            self.aesthetic,
            f"{self.subject_descriptor}, {self.subject_features}",
            f"{self.subject_pose}",
            self.wardrobe_description,
            self.location_description,
            f"{self.lighting_type}: {self.lighting_description}",
            SKIN_REALISM,
            IDENTITY_LOCK,
        ]
        if self.imperfections:
            parts.append(self.imperfections)
        parts.append(f"Hex Palette: {', '.join(self.hex_palette)}")
        return ", ".join(parts)

    def build_negative(self) -> str:
        return self.negative_prompt

    def to_dict(self) -> dict:
        return {
            "prompt_details": {
                "meta": {
                    "quality": self.camera,
                    "style": self.aesthetic,
                    "aspect_ratio": self.aspect_ratio,
                },
                "subject": {
                    "framing": self.aesthetic,
                    "features": f"{self.subject_descriptor}, {self.subject_features}",
                },
                "textures_and_details": {
                    "skin": self.subject_features,
                    "wardrobe": f"[{self.wardrobe_style}] {self.wardrobe_description}",
                },
                "expression_and_gaze": {
                    "look": self.subject_pose,
                },
                "mood": self.aesthetic,
                "lighting_and_background": {
                    "lighting": f"{self.lighting_type}: {self.lighting_description}",
                    "background": f"[{self.location_setting}] {self.location_description}",
                },
                "negative_prompt": self.negative_prompt,
                "hex_palette": self.hex_palette,
            },
        }


class PromptEngine:
    """
    Modular prompt generator for ultra-realistic AI influencer photography.

    Usage:
        engine = PromptEngine(seed=None)  # random seed
        prompt = engine.generate()        # single prompt
        prompts = engine.generate_batch(n=5)  # n prompts
    """

    def __init__(
        self,
        seed: int | None = None,
        camera: list[str] | None = None,
        aesthetic: list[str] | None = None,
        subjects: list[dict] | None = None,
        wardrobe: list[dict] | None = None,
        locations: list[dict] | None = None,
        lighting: list[dict] | None = None,
        negatives: str | None = None,
        palettes: list[list[str]] | None = None,
        aspect_ratios: list[str] | None = None,
        use_creative_angles: bool = True,
        use_creative_poses: bool = True,
    ):
        self.rng = random.Random(seed)
        self.camera = camera or MODULE_A_CAMERA
        self.aesthetic = aesthetic or MODULE_B_AESTHETIC
        self.subjects = subjects or MODULE_C_SUBJECT
        self.wardrobe = wardrobe or MODULE_D_WARDROBE
        self.locations = locations or MODULE_E_LOCATION
        self.lighting = lighting or MODULE_F_LIGHTING
        self.negatives = negatives or NEGATIVE_PROMPT
        self.palettes = palettes or HEX_PALETTES
        self.aspect_ratios = aspect_ratios or ASPECT_RATIOS
        # Merge creative angles + poses into the existing pools for variety
        if use_creative_angles:
            self.camera = self.camera + CREATIVE_CAMERA_ANGLES
        if use_creative_poses:
            # Inject creative poses into the first subject's pose list
            if self.subjects:
                self.subjects = [
                    {**s, "poses": s["poses"] + CREATIVE_POSES}
                    for s in self.subjects
                ]

    def generate(self) -> GeneratedPrompt:
        """Generate a single random prompt."""
        # Pick subject first since pose is nested
        subject = self.rng.choice(self.subjects)
        lighting_choice = self.rng.choice(self.lighting)
        # Imperfections only make sense with certain lighting combos
        imperfections = (
            lighting_choice["description"]
            if "low-resolution" in lighting_choice["description"]
            or "lens glare" in lighting_choice["description"]
            else None
        )

        return GeneratedPrompt(
            camera=self.rng.choice(self.camera),
            aesthetic=self.rng.choice(self.aesthetic),
            subject_descriptor=subject["descriptor"],
            subject_features=subject["features"],
            subject_pose=self.rng.choice(subject["poses"]),
            wardrobe_style=self.rng.choice(self.wardrobe)["style"],
            wardrobe_description=self.rng.choice(self.wardrobe)["description"],
            location_setting=self.rng.choice(self.locations)["setting"],
            location_description=self.rng.choice(self.locations)["description"],
            lighting_type=lighting_choice["type"],
            lighting_description=lighting_choice["description"],
            imperfections=imperfections,
            hex_palette=self.rng.choice(self.palettes),
            aspect_ratio=self.rng.choice(self.aspect_ratios),
            negative_prompt=self.negatives,
        )

    def generate_carousel(
        self,
        n: int = 3,
        location_setting: str | None = None,
        location_description: str | None = None,
        wardrobe_style: str | None = None,
        wardrobe_description: str | None = None,
        aesthetic: str | None = None,
    ) -> list[GeneratedPrompt]:
        """Generate n prompts for a single outing — same outfit, same identity,
        same location across all slides. Only camera angle, pose, and lighting rotate.

        Args:
            n: number of slides
            location_setting/wardrobe_style/aesthetic: optional constraints
            location_description: full description of the location (overrides random)
            wardrobe_description: full description of the outfit (overrides random)
        """
        # Lock ONE subject, ONE outfit, ONE location across all slides
        subject = self.rng.choice(self.subjects)
        wardrobe = self.rng.choice(self.wardrobe)
        if wardrobe_style:
            matches = [w for w in self.wardrobe if w["style"] == wardrobe_style]
            if matches:
                wardrobe = self.rng.choice(matches)
        if wardrobe_description:
            wardrobe = {"style": wardrobe.get("style", "Custom"), "description": wardrobe_description}

        location = self.rng.choice(self.locations)
        if location_setting:
            matches = [l for l in self.locations if l["setting"] == location_setting]
            if matches:
                location = self.rng.choice(matches)
        if location_description:
            location = {"setting": location.get("setting", "Custom"), "description": location_description}

        aest = self.rng.choice(self.aesthetic)
        if aesthetic:
            aest = aesthetic

        prompts = []
        for i in range(n):
            lighting_choice = self.rng.choice(self.lighting)
            imperfections = (
                lighting_choice["description"]
                if "low-resolution" in lighting_choice["description"]
                or "lens glare" in lighting_choice["description"]
                else None
            )
            # Append wardrobe + hair lock to description for cross-slide consistency
            wardrobe_desc = wardrobe["description"] + ". " + WARDROBE_LOCK_SUFFIX
            p = GeneratedPrompt(
                camera=self.rng.choice(self.camera),
                aesthetic=aest,
                subject_descriptor=subject["descriptor"],
                subject_features=subject["features"] + ". " + HAIR_LOCK_SUFFIX,
                subject_pose=self.rng.choice(subject["poses"]),
                wardrobe_style=wardrobe["style"],
                wardrobe_description=wardrobe_desc,
                location_setting=location["setting"],
                location_description=location["description"],
                lighting_type=lighting_choice["type"],
                lighting_description=lighting_choice["description"],
                imperfections=imperfections,
                hex_palette=self.rng.choice(self.palettes),
                aspect_ratio=self.rng.choice(self.aspect_ratios),
                negative_prompt=self.negatives,
            )
            prompts.append(p)
        return prompts

    def generate_batch(self, n: int = 5) -> list[GeneratedPrompt]:
        """Generate n random prompts."""
        return [self.generate() for _ in range(n)]


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Ultra-Realistic Prompt Engine — SOUL 2 / Z Studio aesthetic generator"
    )
    p.add_argument(
        "--count", "-n", type=int, default=5,
        help="Number of prompts to generate (default: 5)"
    )
    p.add_argument(
        "--format", "-f", type=str, choices=["text", "json"], default="text",
        help="Output format: 'text' (natural language) or 'json' (structured) (default: text)"
    )
    p.add_argument(
        "--seed", "-s", type=int, default=None,
        help="Random seed for reproducible output"
    )
    p.add_argument(
        "--style", choices=["casual", "winter", "y2k", "high-fashion", "slow-living",
                            "smart-casual", "founder-mode", "tech-minimal", "city-walk",
                            "editorial-knit"], default=None,
        help="Constrain wardrobe style (default: random)"
    )
    p.add_argument(
        "--aesthetic", choices=["candid", "y2k-nostalgia", "luxury-casual", "sporty", "editorial"], default=None,
        help="Constrain aesthetic (default: random)"
    )
    p.add_argument(
        "--generate", "-g", action="store_true",
        help="Generate images via FAL after building prompts (requires FAL_KEY)"
    )
    p.add_argument(
        "--carousel", "-c", action="store_true",
        help="Generate a carousel (same outfit + location across all slides)"
    )
    p.add_argument(
        "--location", "-l", type=str, default=None,
        help="Location description for carousel mode (e.g. 'Covent Garden market hall in London')"
    )
    p.add_argument(
        "--outfit", type=str, default=None,
        help="Outfit description for carousel mode (e.g. 'Oversized cream knit sweater and wide-leg jeans')"
    )
    return p


def _filter_subjects(constraint: str | None) -> list[dict]:
    # Only Aeloria now — no ethnicity filter
    return MODULE_C_SUBJECT


def _filter_wardrobe(constraint: str | None) -> list[dict]:
    if constraint is None:
        return MODULE_D_WARDROBE
    style_map = {
        "casual": "Casual/Street",
        "winter": "Winter",
        "y2k": "Y2K/Glam",
        "high-fashion": "High Fashion",
        "slow-living": "Slow Living",
        "earthy-linen": "Earthy Linen",
        "founder-mode": "Founder Mode",
        "travel-chic": "Travel Chic",
        "athleisure": "Athleisure",
        "editorial-knit": "Editorial Knit",
    }
    target = style_map.get(constraint)
    return [w for w in MODULE_D_WARDROBE if w["style"] == target]


def _filter_aesthetic(constraint: str | None) -> list[str]:
    if constraint is None:
        return MODULE_B_AESTHETIC
    aesthetic_map = {
        "candid": "Ultra-realistic candid street portrait",
        "y2k-nostalgia": "Colorful glam early-2000s snapshot, grainy low-res nostalgia",
        "luxury-casual": "Luxury casual street style aesthetic",
        "sporty": "Clean sporty fashion aesthetic",
        "editorial": "Bold fashion editorial aesthetic",
    }
    target = aesthetic_map.get(constraint)
    return [a for a in MODULE_B_AESTHETIC if a == target] or MODULE_B_AESTHETIC


def _generate_images(prompts: list[GeneratedPrompt]) -> list[str]:
    """Generate images via FAL juggernaut-flux-lora + Aeloria LoRA."""
    import os
    import time
    import io

    import fal_client
    import httpx
    from PIL import Image, ImageEnhance, ImageFilter
    import numpy as np
    from dotenv import load_dotenv

    load_dotenv()
    os.environ["FAL_KEY"] = os.environ["FAL_KEY"]
    lora_url = os.environ["AELORIA_LORA_URL"]

    out_dir = "output/prompt_engine"
    os.makedirs(out_dir, exist_ok=True)
    paths = []

    for i, p in enumerate(prompts):
        prompt_text = p.build_text()
        seed = random.randint(0, 2**31)
        print(f"  [{i+1}/{len(prompts)}] seed={seed} generating...")
        t0 = time.time()

        result = fal_client.subscribe("rundiffusion-fal/juggernaut-flux-lora", arguments={
            "prompt": prompt_text,
            "loras": [{"path": lora_url, "scale": 0.7}],
            "guidance_scale": 3.5,
            "num_inference_steps": 40,
            "image_size": "portrait_4_3",
            "num_images": 1,
            "enable_safety_checker": False,
            "seed": seed,
        })
        elapsed = time.time() - t0
        print(f"    done in {elapsed:.1f}s")

        img_url = result["images"][0]["url"]
        resp = httpx.get(img_url, timeout=120)
        img = Image.open(io.BytesIO(resp.content))

        # Post-process
        img = ImageEnhance.Color(img).enhance(0.95)
        img = ImageEnhance.Brightness(img).enhance(1.03)
        img = ImageEnhance.Contrast(img).enhance(1.05)
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        w, h = img.size
        arr = np.array(img, dtype=np.float32) / 255.0
        cy, cx = h / 2, w / 2
        max_r = (cx**2 + cy**2) ** 0.5
        yy, xx = np.ogrid[:h, :w]
        dist = ((xx - cx)**2 + (yy - cy)**2) ** 0.5 / max_r
        vignette = np.clip(1 - 0.15 * dist, 0.7, 1.0)
        arr *= vignette[..., np.newaxis]
        img = Image.fromarray((arr * 255).clip(0, 255).astype(np.uint8))

        out_path = os.path.join(out_dir, f"aeloria_prompt_{i+1:03d}.png")
        img.save(out_path, "PNG")
        print(f"    saved: {out_path}")
        paths.append(out_path)

    return paths


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    engine = PromptEngine(
        seed=args.seed,
        subjects=_filter_subjects(None),  # always Aeloria
        wardrobe=_filter_wardrobe(args.style),
        aesthetic=_filter_aesthetic(args.aesthetic),
    )

    if args.carousel:
        prompts = engine.generate_carousel(
            n=args.count,
            location_description=args.location,
            wardrobe_description=args.outfit,
            aesthetic=args.aesthetic,
        )
    else:
        prompts = engine.generate_batch(n=args.count)

    if args.format == "json":
        output = [p.to_dict() for p in prompts]
        print(json.dumps(output, indent=2))
    else:
        for i, p in enumerate(prompts, 1):
            print(f"=== Prompt {i} ===")
            print(p.build_text())
            print()
            print("Negative:", p.build_negative())
            print()

    if args.generate:
        print("\nGenerating images via FAL...\n")
        paths = _generate_images(prompts)
        print(f"\nDone! {len(paths)} images saved to output/prompt_engine/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
