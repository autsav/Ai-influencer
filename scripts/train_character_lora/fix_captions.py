"""Fix training captions — replace garbage BLIP-2 output with proper visual_dna descriptions.

The BLIP-2 captions were unusable ("frng frng frng", "messy bun and a messy bun").
This script writes proper captions using the visual_dna fields from aeloria.yaml,
varying pose/expression/wardrobe per image for dataset diversity.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
META_PATH = ROOT / "data" / "train_metadata.jsonl"

# Visual DNA from aeloria.yaml
HAIR = "auburn hair pulled up in a loose messy bun, loose pieces framing her face"
EYES = "green eyes"
SKIN = "fair skin with freckles across nose and cheeks, visible pores and peach fuzz"
BODY = "young woman in her mid-twenties, slender build"

# Vary expressions across images for diversity
EXPRESSIONS = [
    "a warm half-smile, eyes forward, aware of the camera but not performing for it",
    "a calm, unbothered gaze into the middle distance",
    "a direct look — present and slightly guarded at once",
    "a caught-off-guard laugh, surprised by her own reaction",
    "a knowing look back over one shoulder",
    "a spontaneous grin catching her off guard",
    "eyes closed, head tilted back, relaxed and unguarded",
    "a warm half-smile, looking slightly away from camera",
]

# Vary poses
POSES = [
    "standing at a relaxed angle, weight slightly shifted, at ease",
    "mid-stride walking forward, natural unhurried motion",
    "glancing back over one shoulder with a knowing half-smile",
    "one hand resting on a hip, chin lifted, calm and self-assured",
    "leaning casually against a surface, effortlessly composed",
    "caught mid-laugh, genuine and unposed",
    "seated in profile, looking into the middle distance, lost in thought",
    "arms loosely crossed, direct gaze into the lens, quiet confidence",
    "hand pushed back through hair, thoughtful gesture",
    "standing straight, arms relaxed at her sides, open posture",
    "sitting casually, one leg crossed over the other",
    "adjusting gold hoop earring while thinking",
    "pushing hair back from her face with one hand",
    "holding a near-empty mug of tea, forgotten",
    "looking down with a soft smile, hands in pockets",
    "looking up at the sky, serene expression",
]

# Vary wardrobe
WARDROBES = [
    "earthy knit sweater, linen pants, gold hoop earrings",
    "oversized cream cardigan, brown linen trousers",
    "olive green turtleneck, dark jeans, gold hoop earrings",
    "beige linen blouse, brown belt, natural makeup",
    "thick grey wool sweater, messy bun, no jewelry",
    "floral midi dress, denim jacket draped over shoulders",
    "white cotton blouse, brown suspenders, gold earrings",
    "terracotta-colored knit top, linen skirt",
    "navy blue turtleneck, beige trench coat, gold earrings",
    "rust-colored sweater, dark denim, gold hoops",
    "cream cable-knit sweater, brown corduroy pants",
    "sage green linen shirt, natural fabric, gold earrings",
    "burgundy turtleneck, dark trousers, minimal makeup",
    "charcoal grey sweater, messy bun, gold hoop earrings",
    "camel coat over white blouse, brown belt",
    "denim shirt with rolled sleeves, brown belt, gold earrings",
]

# Vary lighting/mood
LIGHTING = [
    "soft directional sunlight, warm golden hour glow",
    "natural window light, soft shadows on one side of face",
    "overcast diffused light, even and gentle on skin",
    "warm afternoon backlight creating a halo around hair",
    "cool morning light, soft and muted tones",
    "dappled shade with patches of warm light on skin",
    "soft indoor lighting, warm and intimate",
    "bright but diffused daylight, natural and unposed",
]

# Base trigger phrase for LoRA — consistent across all images
TRIGGER = "aeloria woman"

records = []
with open(META_PATH) as f:
    for line in f:
        records.append(json.loads(line))

print(f"Rewriting {len(records)} captions...")

for i, rec in enumerate(records):
    # Use different modular bases so combos don't repeat in cycles
    expr = EXPRESSIONS[i % len(EXPRESSIONS)]
    pose = POSES[(i * 3 + 1) % len(POSES)]
    wardrobe = WARDROBES[(i * 5 + 2) % len(WARDROBES)]
    lighting = LIGHTING[(i * 2 + 1) % len(LIGHTING)]

    # Build a rich, SD1.5-friendly caption
    caption = (
        f"{TRIGGER}, {BODY}, {HAIR}, {EYES}, "
        f"{SKIN}, {expr}, {pose}, "
        f"wearing {wardrobe}, {lighting}, "
        f"photorealistic, detailed skin texture, natural lighting"
    )
    rec["caption"] = caption

# Write back
with open(META_PATH, "w") as f:
    for rec in records:
        f.write(json.dumps(rec) + "\n")

# Show samples
for i in [0, 8, 16, 24]:
    if i < len(records):
        print(f"\n[{i}] {records[i]['file_name'][:30]}...")
        print(f"    {records[i]['caption']}")

print(f"\n✅ Rewrote {len(records)} captions")