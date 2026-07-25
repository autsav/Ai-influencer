"""
Ultra-realistic prompt engine for Aeloria image generation.

Converts simple scene descriptions into anti-plastic photography prompts
following the 5 core rules:
1. STRIP beauty words
2. ADD physical imperfections  
3. SPECIFY real camera hardware & film stock
4. ENFORCE physical lighting & optics
5. ENSURE scene logic & geometry

Usage:
    from aeloria.generation.realistic_prompt_engine import build_realistic_prompt
    positive, negative = build_realistic_prompt("sitting at a café in Notting Hill")
"""
from __future__ import annotations

import random

# ── Aeloria's fixed physical identity (LoRA handles face, this guides texture) ─
AELORIA = {
    "age": "24-year-old",
    "hair": "auburn hair pulled up in a loose messy bun with flyaway strands, loose pieces framing her face",
    "eyes": "green eyes",
    "skin": "fair skin with freckles across nose and cheeks",
    "build": "slender build",
    "extras": "gold hoop earrings",
}

# ── Camera + lens + film stock combos (real hardware) ─────────────────────────
CAMERA_COMBOS = [
    ("Canon EOS R5", "85mm f/1.8 lens", "Kodak Portra 400 film stock, neutral color grade"),
    ("Leica M10", "50mm f/1.4 lens", "Kodak Portra 400 film stock"),
    ("Hasselblad H6D", "85mm f/2.8 lens", "Fujifilm Pro 400H film stock"),
    ("Leica M11", "35mm f/1.4 Summilux lens", "Kodak Gold 200 film stock"),
    ("Sony A7R V", "85mm f/1.4 GM lens", "Cinestill 800T film stock"),
    ("Nikon Z9", "50mm f/1.4 lens", "Fujifilm Pro 400H film stock, neutral color grade"),
    ("Canon EOS R5", "35mm f/1.4 lens", "Kodak Portra 800 film stock"),
]

# ── Lighting setups (physical, directional, with catchlight logic) ────────────
LIGHTING = [
    "soft diffused directional daylight from cloudy skies, even exposure on face, natural catchlights from sky reflection in both pupils",
    "side daylight from camera left at 3pm, soft golden hour, natural shadows on right side of face, matching circular pupil reflections",
    "warm window light from camera right at 4pm, soft directional shadows on left side of face, circular catchlights from window reflection in both pupils",
    "backlit golden hour at 6pm, warm rim light on hair edges, face in soft shadow with natural fill from sky, catchlights from sun reflection",
    "overcast diffused daylight at 11am, soft shadows, even exposure, natural catchlights from bright overcast sky in both pupils",
    "warm ambient lighting mixed with overhead spotlights, natural skin oil highlights, circular catchlights from overhead source",
    "cool morning light at 8am, muted tones, gentle shadows under nose and chin, catchlights from bright sky",
]

# ── Physical imperfections (rotated to avoid repetition) ──────────────────────
IMPERFECTIONS = [
    "natural skin texture with subtle forehead perspiration, fine laugh lines around the eyes, natural facial asymmetry, realistic pore structure, stray hair strands, natural skin oil highlights",
    "realistic skin texture showing fine pores, natural cheek redness from cool air, slight fine lines around the eyes, soft organic face shape with natural asymmetry, single flyaway hair strands catching moisture, individual eyelashes, matte skin finish with subtle nose highlights",
    "visible pores, slight forehead shine, subtle fine lines around eyes, peach fuzz on upper lip, mild redness on cheeks, slight asymmetry in smile, one eye slightly more open than the other",
    "natural skin texture, fine smile lines, subtle nostril flare, uneven brow arch, mild under-eye shadows, slight chin crease, realistic skin oil highlights on nose and forehead",
    "fine lines at eye corners, subtle nose-to-mouth fold, realistic pore structure, chapped lower lip, natural brow texture, stray flyaway hairs, slight wind flush on cheeks",
    "subtle perspiration on forehead, natural skin texture with visible pores, fine lines around eyes and mouth, slight facial asymmetry, stray hairs escaping from bun, natural skin oil on T-zone",
]

# ── Optical characteristics ───────────────────────────────────────────────────
OPTICS = [
    "natural optical depth of field, subtle film grain, unpolished photojournalism style",
    "shallow natural depth of field, subtle film grain, faint chromatic aberration at edges, raw uncompressed photo",
    "medium format depth of field, fine film grain, natural color rendition, raw photo",
    "natural depth of field, subtle lens vignetting, fine grain structure, slight optical softness at edges",
]

# ── Candid / motion elements ──────────────────────────────────────────────────
CANDID = [
    "candid unposed moment, slight motion blur on her hand",
    "caught mid-stride, natural unhurried motion, genuine expression",
    "unposed, caught off-guard, natural relaxed posture",
    "candid street photography, slight motion blur on passing pedestrian behind her",
    "genuine mid-laugh moment, unposed, natural body language",
    "raw documentary photograph, unposed, natural interaction with environment",
]

# ── Scene geometry enforcement ────────────────────────────────────────────────
GEOMETRY = [
    "straight architectural lines in background, clear separation between foreground and background",
    "real background depth, legible environmental details without distorted geometry",
    "natural fabric draping, functional clothing seams, clear foreground-background separation",
    "real reflective logic on surfaces, straight lines, natural material textures in environment",
]

# ── Universal negative prompt (strict AI artifact exclusion) ──────────────────
NEGATIVE_PROMPT = (
    "smooth plastic skin, airbrushed, beauty filter, fake teeth, fused fingers, "
    "asymmetric pupils, mismatched eye catchlights, glossy ceramic skin, "
    "CGI, 3D render, digital illustration, unreal engine, smooth Gaussian blur, "
    "distorted background geometry, floating objects, pseudotext, "
    "oversaturated colors, studio lighting, vector art, perfect symmetry, "
    "porcelain skin, porcelain face, vector style, digital painting, "
    "perfect hair, smooth skin filter, missing fingers, extra digits, "
    "continuous band of teeth, dead eyes, glassy eyes, mismatched eye reflections, "
    "melted background, floating rain droplets, HDR bloom, hyper-saturated, "
    "anime, render, 3D model, beautiful, stunning, perfect, masterpiece, "
    "hyperrealistic, photorealistic, 8k, 4k, wax, mannequin, doll-like, "
    "ring light, artificial rim light, oversharpened, digital noise, banding, "
    "watermark, text, signature, frame, border, logo, posed, stiff, rigid posture, "
    "plastic skin, waxy skin, retouched, over-polished, beauty marks removed, "
    "blurry background, bokeh balls, Gaussian blur, TAA artifacts"
)


def build_realistic_prompt(
    scene: str,
    wardrobe: str = "",
    seed: int | None = None,
) -> tuple[str, str]:
    """
    Transform a simple scene description into an ultra-realistic photography prompt.
    
    Args:
        scene: Simple user description (e.g. "sitting at a café in Notting Hill")
        wardrobe: Optional wardrobe override (e.g. "red leather jacket, black jeans")
        seed: For deterministic prompt variation (same seed = same camera/lighting)
    
    Returns:
        (positive_prompt, negative_prompt) tuple ready for FAL/ComfyUI
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    
    camera, lens, film = rng.choice(CAMERA_COMBOS)
    lighting = rng.choice(LIGHTING)
    imperfection = rng.choice(IMPERFECTIONS)
    optics = rng.choice(OPTICS)
    candid = rng.choice(CANDID)
    geometry = rng.choice(GEOMETRY)
    
    # Build wardrobe with fabric logic
    if wardrobe:
        wardrobe_text = f"wearing {wardrobe} with visible fabric weave, functional seams, and natural fabric draping"
    else:
        wardrobe_text = "wearing a worn knit sweater with visible fabric weave, functional seams, and natural fabric draping"
    
    positive = (
        f"Raw, candid photograph of a {AELORIA['age']} woman, {scene}. "
        f"Captured on a {camera} with a {lens}, {lighting}. "
        f"Subject details: {imperfection}. "
        f"Matching circular pupil reflections, natural sclera texture, individual eyelashes. "
        f"{AELORIA['hair']}, {AELORIA['eyes']}, {AELORIA['skin']}, {AELORIA['extras']}. "
        f"{wardrobe_text}. "
        f"Background shows {geometry}, soft optical background bokeh, subtle lens vignetting. "
        f"Shot on {film}, {optics}, {candid}."
    )
    
    return positive, NEGATIVE_PROMPT