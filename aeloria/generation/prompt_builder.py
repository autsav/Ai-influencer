"""Aeloria image-generation prompt builder.

ARCHITECTURE (Soul 2.0):
  - Identity  → entirely from trained LoRA (aeloria_lora_url). Text NEVER encodes identity.
  - Appearance → visual_dna fields from aeloria.yaml (hair, eyes, skin, palette).
  - Scene/Wardrobe/Location → user-provided overrides ONLY (brief fields).
  - Mood/Camera/Style → user-provided overrides OR deterministic hash pick.
  - Backstory/lore → NEVER enters this file. NOT loaded from persona.

PROMPT ORDER: opener → angle → subject+scene → lighting → pose → expression
            → aura → skin → outfit → camera → film → texture → avoid

THREE SIGNATURE STYLES (deterministic per-brief hash, biased by pillar):
  - film_editorial: warm-cool cinematic, shallow depth, editorial framing
  - flash_candid:    raw disposable-camera flash, overexposed skin, heavy grain
  - paparazzi_night: low-light telephoto, skin-only warmth against near-black
"""
import hashlib

from aeloria.persona.loader import Persona

# ── Physical appearance pools (never backstory, never lore) ──────────────────

# Neutral poses: location-independent, work in any scene the user sets.
_POSSIBLE_POSES = [
    "standing at a relaxed angle, weight slightly shifted, at ease",
    "mid-stride walking forward, natural unhurried motion",
    "glancing back over one shoulder with a knowing half-smile",
    "one hand resting on a hip, chin lifted, calm and self-assured",
    "leaning casually against a wall or surface, effortlessly composed",
    "caught mid-laugh, genuine and unposed",
    "seated in profile, looking into the middle distance, lost in thought",
    "arms loosely crossed, direct gaze into the lens, quiet confidence",
    "hand pushed back through hair, thoughtful gesture",
    "standing straight, arms relaxed at her sides, open posture",
]

_POSSIBLE_EXPRESSIONS = [
    "a warm half-smile, eyes forward, aware of the camera but not performing for it",
    "a spontaneous grin catching her off guard",
    "a calm, unbothered gaze into the middle distance",
    "a direct look — present and slightly guarded at once",
    "a caught-off-guard laugh, surprised by her own reaction",
    "eyes closed, head tilted back, relaxed and unguarded",
    "a knowing look back over one shoulder",
    "a relaxed open expression, gently curious",
    "a quiet, confident smile, not performed",
]

_POSSIBLE_MANNERISMS = [
    "pushing hair back from her face with one hand",
    "adjusting an earring while thinking",
    "resting one hand on a hip",
    "looking slightly off-camera, contemplative",
    "a casual gesture, hands moving naturally",
    "pausing mid-motion, caught in thought",
]

_POSSIBLE_PROPS = [
    "a MacBook Pro open on the desk",
    "a ceramic coffee mug held loosely",
    "a minimal dotted notebook with workflow sketches",
    "a pair of earbuds, one in, one dangling",
    "a simple leather strap watch catching the light",
    "a black technical backpack slung over one shoulder",
    "", "", "",  # ~1/3 of shots carry no prop
]

# Hair states — physical description only, no scene context.
_POSSIBLE_HAIR = [
    "auburn hair falling loose across her shoulders",
    "auburn hair in a loose high bun, strands escaping",
    "auburn hair in a messy low bun, loose strands framing her face",
    "auburn hair half-up, loose strands framing her face",
    "auburn hair loose and wind-tousled",
]

# Outfit pool — smart casual, neutral colours. Same female character.
_POSSIBLE_OUTFITS = [
    "a charcoal crew-neck t-shirt under a navy structured overshirt, clean white sneakers, gold hoop earrings",
    "an olive green henley with rolled sleeves, dark denim jeans, minimal leather sneakers, gold hoop earrings",
    "a white t-shirt under a charcoal blazer-style overshirt, navy trousers, white sneakers",
    "a navy crew-neck sweater over a white t-shirt, dark chinos, clean sneakers, gold hoop earrings",
    "a black t-shirt under a grey cardigan, dark jeans, minimal sneakers",
    "a cream turtleneck under a black overshirt, charcoal trousers, white sneakers, gold hoop earrings",
    "a grey crew-neck t-shirt under an olive overshirt, dark denim, neutral sneakers",
    "a navy polo shirt, dark chinos, white sneakers, a simple watch",
    "a white henley, charcoal trousers, a black technical jacket slung over",
    "a dark green t-shirt under a cream overshirt, dark jeans, brown leather sneakers, gold hoop earrings",
    "a black t-shirt, grey trousers, a navy overshirt open at the front, gold hoop earrings",
    "a charcoal hoodie under a black bomber jacket, dark jeans, white sneakers",
    "a white t-shirt under a beige overshirt, olive chinos, white sneakers",
    "a navy t-shirt, dark denim, a grey overshirt, minimal accessories, gold hoop earrings",
]

_FILMS = ["Kodak Portra 400", "Kodak Portra 800", "Cinestill 800T", "Fujifilm Pro 400H", "Kodak Gold 200"]

# Skin: raw realism texture — no scene light context.
_SKIN = (
    "Her skin stays raw and real — visible pores across the cheeks and nose, "
    "peach fuzz on the upper lip and forehead, vellus hair on the T-zone and cheeks, "
    "fine texture on the forehead and around the nostrils, a natural skin tone "
    "with subtle variation, faint under-eye darkness, slight redness at the nose "
    "wings, and real pore-level detail everywhere, flyaway hairs catching the light. "
    "No smoothing, no beauty filter, no plastic. Real skin texture preserved."
)
_AVOID = (
    "Avoid: blank dull expression, stiff centered pose, airbrushed skin, plastic skin, waxy skin, "
    "beauty filter, CGI look, distorted anatomy, exaggerated proportions, duplicate limbs, low resolution. "
    "Do not change her facial features or body shape."
)

# Mood tones — PURE MOOD, no scene description. Overridden entirely by mood_override.
_PILLAR_MOOD = {
    "ai_workflows":      "focused, absorbed in building, quiet determination",
    "ai_tools":          "curious, evaluating, slightly excited",
    "case_studies":      "confident, satisfied, proud of the result",
    "founder_lifestyle": "relaxed, approachable, naturally confident",
    "future_of_business":"contemplative, forward-thinking, engaged",
}

# ── Style: film_editorial ─────────────────────────────────────────────────────
_FILM_ANGLES = [
    "a bold low hero angle from below with a slight camera tilt, making her feel tall",
    "an intimate extreme close crop on her face and shoulders so every texture reads",
    "an off-center composition with her at one edge, the space around her breathing",
    "a candid over-the-shoulder frame as she turns back toward the lens mid-motion",
    "a three-quarter angle catching her mid-step",
    "a wide-angle frame showing her full length in context",
    "a top-down overhead angle looking straight down, a graphic editorial composition",
    "a long-exposure feel with soft directional light, cinematic and clean",
]
_FILM_ATMOS = [
    "warm amber golden-hour light, cool tones bleeding at the frame edges",
    "flat soft overcast light, even and gentle across her face",
    "crisp natural golden-hour light with clean shadows and warm glossy highlights on the skin",
    "warm directional morning light from camera-left, a luminous rim of light along hair and jaw",
    "a breathtaking soft sky behind her",
    "misty soft diffused light and gentle fog in the background",
]
_FILM_LENSES = ["an 85mm lens look", "a 50mm lens look", "a 35mm lens look", "a 50mm lens look with shallow depth of field"]
_FILM_TEXTURE = "subtle film grain, natural preserved skin texture with pores and fine detail, a raw unretouched look, faint sensor noise"

# ── City catalogue (activated when brief["location"] is set) ─────────────────
_CITY_ANGLES = [
    "a long-lens compression shot from across the street, London's skyline towers behind her",
    "an eye-level candid frame as she walks past a classic red telephone box on a cobbled street",
    "a three-quarter angle with Tower Bridge or the London Eye in the soft background",
    "a documentary-style street shot, her leaning against a brick wall in Shoreditch",
    "a wide-angle frame from a rooftop bar terrace overlooking the city at dusk",
    "a candid over-the-shoulder shot as she browses a street market stall in Borough Market",
    "a cinematic low-angle with Westminster's gothic architecture rising behind her",
    "a relaxed walking pose on a sunlit pavement, Regent Street or Carnaby Street behind her",
    "a reflective close-up portrait against a blurred London skyline backdrop at magic hour",
    "a candid frame as she sits on the embankment wall, the Thames behind her",
]
_CITY_ATMOS = [
    "warm late-afternoon golden-hour light washing over the city, long soft shadows on the pavement",
    "soft diffused overcast light, even and flattering, the city muted and gentle in the background",
    "magic-hour warmth with a honey-gold glow on her skin and the city skyline lit behind her",
    "cool crisp morning light on a brick-lined street, the city waking up around her",
    "a moody overcast afternoon with soft grey city light, atmospheric and cinematic",
    "dappled sunlight filtering through urban tree canopy on a residential street",
    "the last rays of sunset catching the city skyline in amber and rose gold",
]
_CITY_GRADE = [
    "a warm golden-hour grade of amber and honey over cool city greys (#1a1a1a, #4a4a4a, #d4a853, #e8c4a0)",
    "a cool cinematic grade of slate blues and warm skin tones (#0d1117, #2d3748, #a0aec0, #fbd38d)",
    "a desaturated editorial grade with punchy contrast (#1c1c1c, #4a5568, #a0aec0, #f7fafc)",
    "a rich warm grade of deep shadows and golden highlights (#0f0f0f, #7c5c3e, #d4a574, #f5e6d3)",
]
_CITY_TEXTURE = "clean modern digital capture, sharp city detail in the background, natural preserved skin texture with pores and fine detail, a raw unretouched editorial look"

# ── Style: flash_candid ───────────────────────────────────────────────────────
_FLASH_ANGLES = [
    "shot handheld with a direct on-camera flash at chest level, the framing tilted and crooked and spontaneous",
    "a low handheld angle with a harsh direct flash, off-center and a little chaotic",
    "captured on a phone with the flash on, arm at chest height, a raw point-and-shoot snap",
    "a candid disposable-camera frame, slightly crooked, the flash blowing out the highlights",
    "a flash-lit selfie held at arm's length, tilted and unstudied",
]
_FLASH_LIGHT = [
    "a harsh cold-white on-camera flash blows her skin out to a bright overexposed glow, crushing the background into deep shadow with hard sharp-edged shadows, brutal high contrast and punchy oversaturated color",
    "a sudden blinding point-blank flash washes her skin near-white and bleeds into pitch-dark surroundings, hard-edged shadows stabbing behind her, raw and a little unflattering in the best way",
    "the cheap flash slams flat light onto her face, overexposing the highlights and revealing every pore while the background falls to dark shadow, deep crushed shadows and vivid saturation",
]
_FLASH_TEXTURE = (
    "thick heavy film grain and scattered white flecks of chemical dust, blown-out highlights and crushed blacks, "
    "a strong dark vignette closing in from the edges, the gritty unpolished look of a cheap disposable-camera flash "
    "in bright daylight — raw, immediate and a little unflattering, like a candid moment shared the second after it was taken, "
    "a real unedited phone photo"
)

# ── Style: paparazzi_night ───────────────────────────────────────────────────
_PAP_ANGLES = [
    "a candid telephoto shot from across the street, the scene compressed and slightly voyeuristic",
    "an eye-level mid-range documentary frame, caught unposed as she moves",
    "a low-light candid capture as she steps into an urban scene",
    "a compressed telephoto frame isolating her against a blurred background",
    "a slightly distant candid angle, as if caught by a photographer she never noticed",
    "a three-quarter shot, morning or evening light filtering behind her",
    "a full-length straight-on frame as she walks through the scene",
    "a wide-lens frame, slight fisheye distortion at the edges",
]
_PAP_LIGHT = [
    "dramatic low-light with strong contrast — a gap in the light catching her skin and outfit while everything else falls into deep shadow, her skin tones the only warmth in the frame",
    "moody early-morning urban light, hard pools of light against deep shadow",
    "harsh directional early-morning light raking across her, high contrast, the background sinking into near-dark",
    "a chaotic burst of golden-hour shafts, stark warm light against deep shadows",
    "cool blue-green mist blending with a warm glow, uneven illumination across her face, moody atmosphere",
    "a single warm light source near the frame edge over a muted near-dark background, a mysterious quiet",
    "direct warm light casting hard distinct shadows on the ground, cool grayscale tones with her warm skin the only color",
]
_PAP_GRADE = [
    "a moody color grade of deep shadows and muted urban tones (#070907, #131615, #1c2b16, #3b5f2f) with warm skin the only contrast",
    "a warm golden-hour grade of amber and moss over cool shadows (#0b1a06, #3d5e26, #a4ba4a, #d3ab88, #675349)",
    "a cool misty-night grade of shadow greens and greys (#08100e, #2b3530, #454f45, #c1c6a6)",
    "a golden-hour grade of deep shadow and warm amber cut by morning light (#1a0f05, #7a5010, #8e4a0f, #536b3e, #98a66e)",
    "a muted vintage-film grade of warm browns and moss (#201501, #2f2710, #4e4338, #8a7d69, #776a51)",
    "a teal-and-green grade of near-dark tones (#040a02, #054c30, #035a43, #046e5c, #569494)",
    "a cool grayscale grade with warm skin accents (#181711, #3c3c33, #5f5c50, #f4ede5, #f1d6b7)",
    "a warm earthy grade of creams, greens and earth tones (#100603, #efe9e1, #5d9969, #355479, #dbc2a3)",
]
_PAP_TEXTURE = [
    "sharp digital clarity with fine noise in the shadows, a mood of quiet sophistication, an unposed caught-in-the-moment feel, a real unedited photo",
    "high contrast with a touch of motion blur and a raw candid quality, a real unedited photo",
    "heavy film grain and a vintage golden-hour look, muted and mysterious, a caught-off-guard candid quality, a real unedited photo",
]
_PAP_CAMERA = [
    "a digital camera with a telephoto lens compressing the scene depth",
    "a digital camera with a moderate lens, sharply focused",
    "a wide lens with slight fisheye distortion at the edges",
    "a film camera showing grain and a vintage aesthetic",
]


# ── Mood → expression cues (bias only) ──────────────────────────────────────
_MOOD_EXPR = {
    "determined":      ["daring", "confidence", "mischievous", "grin", "laugh"],
    "focused_playful": ["mischievous", "grin", "half-smile", "playful", "biting back"],
    "joyful":          ["laugh", "grin", "radiant", "crinkled"],
    "relaxed":         ["half-smile", "dreamy", "unguarded", "serene"],
    "serene":          ["serene", "eyes closed", "dreamy", "unguarded"],
    "reflective":      ["dreamy", "unguarded", "half-smile", "gazing"],
    "cool":            ["unbothered", "confidence", "daring", "off to the side"],
}


def _pick(pool: list[str], h: int, salt: int) -> str:
    return pool[(h // salt) % len(pool)]


# Occasional aesthetic variants (kept rare ~1/7 so most posts stay clean editorial).
_NOSTALGIA = [
    "a nostalgic Y2K digicam aesthetic — faint date stamp, hard on-camera flash, early-2000s color",
    "a 90s film-photo aesthetic — warm faded colors, soft grain, vintage snapshot feel",
    "a 70s film aesthetic — golden warm cast, gentle halation and retro grain",
]


def _aesthetic_variant(h: int) -> str:
    r = h % 7
    if r == 0:
        return " Framed as an immersive first-person POV, as if the viewer is right there with her."
    if r == 1:
        return f" Overlay {_NOSTALGIA[(h // 7) % len(_NOSTALGIA)]}, remixed onto her modern styling."
    return ""


# Only these hints HARD-override the pillar mix. "film" is deliberately absent:
# it's a SOFT hint (~35/38 activities hint film/selfie), so a hard film override
# would collapse the feed to ~92% film and starve flash/paparazzi.
_STYLE_FOR_HINT = {
    "paparazzi": "paparazzi_night",
    "flash": "flash_candid",
    "selfie": "film_editorial",
}


def _choose_style(h: int, pillar: str, style_hint: str | None = None) -> str:
    if style_hint in _STYLE_FOR_HINT:
        return _STYLE_FOR_HINT[style_hint]
    r = h % 6
    if pillar == "case_studies" or pillar == "founder_lifestyle":
        return ["film_editorial", "flash_candid", "paparazzi_night",
                "flash_candid", "paparazzi_night", "film_editorial"][r]
    if pillar == "future_of_business":
        return "flash_candid" if r < 3 else "film_editorial"
    return "flash_candid" if r == 0 else "film_editorial"


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def build_prompt(persona: Persona, brief: dict) -> str:
    v = persona.visual_dna
    palette = v.get("palette", "warm natural tones")
    key = str(brief.get("id") or brief.get("prompt_seed", ""))
    h = int(hashlib.md5(key.encode()).hexdigest(), 16)

    style = _choose_style(h, brief.get("pillar", ""), brief.get("style_hint"))

    # Soul 2.0 override wiring — explicit brief fields take absolute precedence
    mood_override = brief.get("mood_override")
    style_override = brief.get("style_override")
    camera_override = brief.get("camera_override")
    location = brief.get("location")
    is_city = bool(location)

    if style_override:
        alias_map = {"candid": "flash_candid", "editorial": "film_editorial",
                     "paparazzi": "paparazzi_night"}
        style = alias_map.get(style_override, style_override)

    # Physical appearance — from visual_dna only, never from backstory
    subject = (
        f"aeloria, a clearly adult woman in her mid-twenties, "
        f"{v['hair']}, {v['eyes']} eyes, {v['skin']}"
    )

    # Scene — user-provided only; mood_override appends mood tone
    seed = brief["prompt_seed"]
    low = seed.lower()
    if low.startswith("aeloria,"):
        seed = seed[len("aeloria,"):].lstrip()
    elif low.startswith("aeloria "):
        seed = seed[len("aeloria"):].lstrip()

    scene = location if is_city else seed
    mood = _PILLAR_MOOD.get(brief.get("pillar") or "", "")
    if mood_override:
        scene = scene + (f", {mood_override}" if scene else mood_override)
    elif not is_city:
        scene = scene + (f", {mood}" if mood else "")

    # Deterministic per-brief picks from physical pools
    pose = _pick(_POSSIBLE_POSES, h, 3)
    expression = _expression_for(h, brief.get("mood"))
    mannerism = _pick(_POSSIBLE_MANNERISMS, h, 37)
    hair_state = _pick(_POSSIBLE_HAIR, h, 13)
    outfit = brief.get("wardrobe") or _pick(_POSSIBLE_OUTFITS, h, 17)
    film = _pick(_FILMS, h, 19)
    prop = _pick(_POSSIBLE_PROPS, h, 7)

    pose_clause = pose + (f", {prop}" if prop else "")
    grade = f"A natural color palette of {palette}"

    # Style-specific branches
    if style == "flash_candid":
        opener = "A raw flash-lit candid snapshot"
        angle = _pick(_FLASH_ANGLES, h, 1)
        light = _pick(_FLASH_LIGHT, h, 11)
        camera = camera_override or "a handheld phone/disposable camera with the flash on"
        texture = _FLASH_TEXTURE

    elif style == "paparazzi_night":
        opener = "A low-light candid paparazzi-style night photograph"
        angle = _pick(_PAP_ANGLES, h, 1)
        light = _pick(_PAP_LIGHT, h, 11)
        camera = camera_override if camera_override else _pick(_PAP_CAMERA, h, 29)
        texture = _pick(_PAP_TEXTURE, h, 31)
        grade = _pick(_PAP_GRADE, h, 23)

    else:  # film_editorial
        opener = "A candid fashion photograph shot on a 50mm lens at f/2.8"
        if is_city:
            angle = _pick(_CITY_ANGLES, h, 1)
            light = _pick(_CITY_ATMOS, h, 11)
            grade = _pick(_CITY_GRADE, h, 23)
            texture = _CITY_TEXTURE
        else:
            angle = _pick(_FILM_ANGLES, h, 1)
            light = _pick(_FILM_ATMOS, h, 11)
            texture = _FILM_TEXTURE
        is_selfie = "selfie" in angle
        camera = camera_override if camera_override else (
            "a front-facing phone camera, 24-35mm look" if is_selfie
            else _pick(_FILM_LENSES, h, 23)
        )

    return (
        f"{opener}, {angle}. Scene: {subject}, {scene}. {light}. "
        f"Pose: {pose_clause}. Expression: {expression}. "
        f"Signature gesture: {mannerism}. "
        f"Preserve aeloria's exact identity — same face, auburn hair and the same recognizable person in every image. "
        f"{_SKIN} — no smoothing, no beauty filter. "
        f"Outfit: {outfit}, styled smart-casual and modern, finished with minimal accessories and gold hoop earrings. "
        f"Shot on {camera}, {film}. {grade}. {texture}.{_aesthetic_variant(h)} "
        f"{_AVOID}."
    )


def _expression_for(h: int, mood: str | None) -> str:
    cues = _MOOD_EXPR.get(mood or "")
    if cues:
        subset = [e for e in _POSSIBLE_EXPRESSIONS if any(c in e for c in cues)]
        if subset:
            return subset[(h // 5) % len(subset)]
    return _pick(_POSSIBLE_EXPRESSIONS, h, 5)
