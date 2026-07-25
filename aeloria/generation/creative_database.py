"""
200 creative camera angles + poses used by fashion editorial, street style,
cinematography, and Instagram lifestyle photographers.

Researched from:
- Fashion editorial: Annie Leibovitz, Mario Testino, Helmut Newton, Steven Meisel, Tim Walker
- Street style: Phil Oh, Tommy Ton, Adam Katz Sinding, Craig Arend
- Cinematography: Dutch angles, dolly zoom, rack focus, low-angle hero shots
- Art photography: Richard Avedon, Irving Penn, Guy Bourdin, Sarah Moon
- Instagram lifestyle: most engaging pose patterns 2024-2026

100 camera angles + 100 poses = 200 total creative variations.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# 100 CREATIVE CAMERA ANGLES & COMPOSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

CREATIVE_CAMERA_ANGLES = [
    # ── Dutch / tilted angles (1-10) ──────────────────────────────────────────────
    "Dutch angle tilted 15 degrees clockwise, subject off-center to the left, negative space on the right filled with environment",
    "Severe 30-degree Dutch tilt, subject positioned in the lower third, dramatic diagonal composition cutting across the frame",
    "Slight 5-degree counter-clockwise tilt, creating subtle visual tension without being obvious, subject centered",
    "Canted Dutch angle with the horizon line running diagonally, subject anchored at the intersection of thirds",
    "Tilted framing where vertical lines in the background run at 20 degrees, creating dynamic unease",
    "Rolling Dutch angle that starts straight then tilts as if the photographer stumbled, caught mid-motion",
    "Reverse Dutch tilt counter-clockwise, subject looking up and to the right, background lines opposing her gaze",
    "Extreme low Dutch angle looking up at the subject from ground level, tilted 25 degrees, heroic but disorienting",
    "Subtle 10-degree tilt with the subject walking along the diagonal, creating forward momentum in a still frame",
    "Mirror Dutch angle — subject reflected in a window or mirror at a different tilt than the main frame",

    # ── Low angles / worm's eye (11-20) ─────────────────────────────────────────
    "Extreme worm's-eye view from ground level looking straight up, subject towering over the camera, sky behind her",
    "Low hero angle from knee height, subject backlit, long shadow stretching toward the camera, heroic framing",
    "Ground-level shot with the camera placed on the floor, subject walking toward the lens, feet entering frame first",
    "Crouching low angle at 30 degrees upward, subject looking down at the camera with authority",
    "Worm's-eye with foreground elements (flowers, steps, puddle) creating depth layers below the subject",
    "Low angle from a staircase looking up, subject ascending, legs and body visible from below, dramatic perspective",
    "Supine camera angle as if lying on the ground, subject stepping over the camera, bold and confrontational",
    "Low three-quarter angle from hip height, capturing the subject mid-stride from below, dynamic foreshortening",
    "Extreme low angle with the subject silhouetted against a bright sky, rim light on her edges from below",
    "Low angle with a reflective surface (puddle, marble floor) creating a mirror image below the subject",

    # ── High angles / bird's eye (21-30) ────────────────────────────────────────
    "Bird's-eye view directly overhead, subject lying on the ground looking up at the camera, graphic top-down composition",
    "High angle from a balcony or bridge looking down at the subject, tiny in a vast environment, scale play",
    "Top-down flat-lay style shot where the subject is part of a larger scene seen from above",
    "45-degree elevated angle from a second-floor window, subject on the street below, voyeuristic editorial feel",
    "Overhead drone-style shot looking straight down, subject as a focal point in a geometric environment",
    "High angle from the top of a staircase, subject at the bottom looking up, vulnerability and scale",
    "Steep 70-degree downward angle, subject sitting on the ground, patterns and textures visible around her",
    "Elevated side angle from a mezzanine, subject in the foreground with the crowd below providing context",
    "Top-down portrait where the subject lies on patterned sheets or grass, hair fanned out around her",
    "Bird's-eye with the subject's shadow as a secondary subject, creating two figures in one frame",

    # ── Over-the-shoulder / behind (31-40) ───────────────────────────────────────
    "Over-the-shoulder shot from behind the subject's right shoulder, her face turned in profile, environment ahead of her",
    "Behind-the-subject frame where her back and hair fill the left third, the scene she's looking at fills the right",
    "Over-the-shoulder with shallow depth of field, subject in focus, what she's looking at blurred in the background",
    "Reverse over-the-shoulder — we see her face, and the person or scene she's looking at is behind the camera",
    "Shot from directly behind the subject as she walks away, her silhouette framed by the environment",
    "Three-quarter from behind, subject turning back to look at the camera over her left shoulder, hair in motion",
    "Behind-and-below angle, looking up at the back of her head and the sky, intimate and unusual",
    "Over-both-shoulders from behind, subject centered, her arms and shoulders framing the composition",
    "Walking-away shot where the subject is small in the lower third, environment dominating the upper two-thirds",
    "Over-the-shoulder with a foreground element (a column, a tree) creating a natural frame on the left edge",

    # ── Extreme close-ups / macro (41-50) ───────────────────────────────────────
    "Extreme close-up on the eyes only, brows and eyes filling the frame, catchlights visible, the rest of the face cropped out",
    "Macro detail shot of hands — her fingers adjusting an earring or touching her hair, nothing else in frame",
    "Close-up on the mouth and chin, lips slightly parted, jawline visible, moody and intimate",
    "Extreme close-up on one eye, the bridge of the nose, and brow, shot from the side at 90 degrees",
    "Detail shot of the collarbone and neck, head cropped above the chin, jewelry catching the light",
    "Macro shot of her hair from behind, individual strands catching sunlight, texture and color visible",
    "Close-up on the ear and earring, hair tucked behind, the gold hoop as the focal point",
    "Partial face frame — only one side of her face visible, split by the frame edge, bold and graphic",
    "Extreme close-up on the lips and the word on her t-shirt, two subjects in tight frame",
    "Detail shot of her wrist and bracelets, hand resting on her hip, skin texture in sharp focus",

    # ── Wide environmental portraits (51-60) ────────────────────────────────────
    "Wide environmental portrait where the subject occupies only 15% of the frame, architecture dominating",
    "Extreme wide shot where the subject is a small figure in a vast landscape, scale and isolation",
    "Wide frame with the subject at the far right edge, 80% of the frame is the environment pulling left",
    "Environmental portrait with the subject framed by a doorway or arch, natural vignette of architecture",
    "Wide shot from across the street, subject small in the frame, city life flowing around her",
    "Subject in the lower left corner, towering architecture or sky filling the rest, tiny human scale",
    "Wide frame where the subject is reflected in a large window, both the reflection and the real person visible",
    "Environmental shot with foreground crowd blurred, subject sharp in the middle ground, background environment in focus",
    "Wide composition using leading lines (railroad tracks, colonnade, bridge) converging on the subject",
    "Subject dwarfed by a massive interior space, chandelier or dome above, standing in a pool of light",

    # ── Reflections / mirrors (61-70) ───────────────────────────────────────────
    "Subject captured only in a mirror reflection, the mirror frame visible, the real subject out of shot",
    "Double exposure — subject's face overlaid on a second scene, dreamy and editorial",
    "Reflection in a shop window, subject superimposed on the display behind the glass, layered composition",
    "Reflection in a puddle after rain, subject looking down, the reflection as the main subject",
    "Split reflection — half the frame is the subject, half is her reflection in a vertical mirror",
    "Reflection in sunglasses where the environment is visible in the lens, subject's face behind",
    "Subject photographed through glass with rain droplets, soft focus and distortion creating mood",
    "Reflection in a chrome or metallic surface, warped and abstract, editorial and avant-garde",
    "Mirror at a 45-degree angle reflecting the subject from above, creating a false bird's-eye view",
    "Subject looking into a mirror, we see both her face and the back of her head simultaneously",

    # ── Motion / blur techniques (71-80) ───────────────────────────────────────
    "Panning shot with the subject sharp and the background streaked in horizontal motion blur",
    "Long exposure where the subject stands still while the crowd flows around her in ghostly blur",
    "Motion blur on the subject's hair and clothes only, face and body sharp, wind effect",
    "Camera blur — intentional camera movement during exposure, painterly abstract result",
    "Zoom burst — zooming during exposure, subject in center sharp, radial blur outward",
    "Subject mid-twirl with the dress and hair spinning, frozen with a fast shutter but motion implied",
    "Double-frame composite — two moments of the subject's movement overlaid, ghosting effect",
    "Slow sync flash — sharp subject with flash, ambient light trails behind from a slow shutter",
    "Subject captured mid-jump, suspended in air, legs bent, hair flying upward, gravity defied",
    "Rear-curtain sync — motion trails following the subject with a sharp flash at the end of the movement",

    # ── Foreground framing (81-90) ─────────────────────────────────────────────
    "Shot through foreground foliage — leaves and branches in soft focus framing the subject in the center",
    "Foreground arch or doorway creating a natural frame within the frame, subject visible through it",
    "Foreground blur of a person passing between camera and subject, momentary obstruction as a creative device",
    "Foreground columns creating a rhythmic pattern, subject visible between two of them in sharp focus",
    "Shot through a foreground object (a glass, a book, flowers) held close to the lens, subject beyond",
    "Foreground shadow falling across the top third of the frame, subject in the lit lower portion",
    "Foreground reflection on a wet surface filling the bottom of the frame, subject above in the real world",
    "Foreground railing or fence creating horizontal lines across the frame, subject behind in focus",
    "Foreground curtain or fabric partially obscuring the subject, peeking through soft material",
    "Foreground hands of another person reaching into frame, subject reacting to the touch",

    # ── Asymmetrical / rule-breaking (91-100) ───────────────────────────────────
    "Subject placed at the extreme bottom-left corner, 90% of the frame is empty sky or wall",
    "Subject's face half-cut by the right edge of the frame, only her left profile visible",
    "Subject positioned in the dead center but everything else in the frame is asymmetrical and off-balance",
    "Negative space composition where the subject is a tiny detail in a vast monochrome field",
    "Subject looking out of frame to the left, with all the environmental interest to her right, opposing",
    "Frame within a frame — subject visible through a small window in a wall, the wall filling most of the shot",
    "Subject's feet at the top of the frame, head at the bottom — upside-down composition",
    "Extreme right-weighted composition with the subject pressed against the edge, looking back into the frame",
    "Subject bisected by a strong vertical line (pillar, shadow edge) splitting the frame into two halves",
    "Off-center subject with the horizon line placed at the very top, 85% of the frame is ground or floor",
]


# ═══════════════════════════════════════════════════════════════════════════════
# 100 CREATIVE POSES & BODY LANGUAGE
# ═══════════════════════════════════════════════════════════════════════════════

CREATIVE_POSES = [
    # ── Dynamic / movement (1-15) ───────────────────────────────────────────────
    "Mid-twirl with one arm extended, dress fanning out, hair whipping around, caught in centrifugal motion",
    "Mid-jump off a low wall or step, knees bent, arms out for balance, suspended in anti-gravity",
    "Running toward the camera, laughing, arms reaching forward, motion and joy frozen in time",
    "Kicking a puddle, water splashing up around her boots, leg extended, playful and candid",
    "Spinning on one foot with the other leg lifted, arms spread wide, full-body spiral",
    "Caught mid-leap over a puddle or curb, one foot up, one down, hair and coat flying",
    "Cartwheel-adjacent — hands reaching toward the ground, body tilted 45 degrees, playful inverted energy",
    "Walking briskly away, looking back over her shoulder, coat billowing behind in the wind",
    "Dancing alone — one arm raised, hip cocked, head tilted, lost in music no one else can hear",
    "Skipping forward, one foot on tiptoe, arms swinging, childlike energy in an adult body",
    "Stretching arms overhead, spine arching, yawning, full-body extension caught candidly",
    "Bending to tie a shoelace, head down, hair falling forward, one knee up, unguarded moment",
    "Twisting at the waist to look behind her, feet planted forward, torso rotated 180 degrees",
    "Sliding on a smooth floor in socks, arms out for balance, delighted and uncontrolled",
    "Hopping over a chain or low barrier, one leg up, hands gripping the top, mid-action",

    # ── Candid / unposed (16-30) ────────────────────────────────────────────────
    "Caught laughing at something off-camera, eyes crinkled, hand half-covering her mouth, genuine",
    "Looking at her phone, completely unaware of the camera, hair falling forward, thumb scrolling",
    "Mid-bite of food — fork or cup halfway to her lips, eyes on the food, unselfconscious",
    "Wiping a smudge off her cheek with the back of her hand, face scrunched in concentration",
    "Fixing a wedged shoe, half-squatting, hand on heel, bag sliding off shoulder, real life",
    "Brushing hair out of her eyes with one hand, wind-blown, squinting, mid-stride",
    "Reaching up to touch a leaf or branch overhead, arm fully extended, on tiptoes, curious",
    "Blowing on a cup of tea or coffee, steam visible, eyes down, both hands cradling the cup",
    "Caught adjusting her bag strap, pulling it up on her shoulder, mouth slightly open in thought",
    "Looking up at the sky, eyes closed, face turned to the sun, absorbing warmth, serene",
    "Pulling a scarf tighter around her neck, chin tucked down, shoulders hunched against cold",
    "Inspecting something on her finger — a ring, a thorn — holding it close to her eyes",
    "Wiping rain off her face with her sleeve, hair wet and clinging, laughing at the weather",
    "Standing on tiptoes to see over a crowd, neck craned, one hand shading her eyes",
    "Caught mid-sneeze or mid-yawn, eyes squeezed shut, nose scrunched, completely unguarded",

    # ── Editorial / sculptural (31-50) ─────────────────────────────────────────
    "Seated with legs crossed, one arm draped over the back of the chair, head resting on hand, languid",
    "Standing against a wall, one foot propped behind her, hands in pockets, shoulders relaxed, cool",
    "Crouching in a three-quarter squat, elbows on knees, hands clasped, gazing at the camera intensely",
    "Lying on her side on a bench or step, head propped on one hand, looking at the camera, odalisque",
    "Standing with one hand on hip, the other tracing her own jawline, contemplative and self-aware",
    "Seated on the ground with knees drawn up, arms wrapped around them, chin resting on knees, compact",
    "Standing in a contrapposto, weight entirely on one leg, the other knee bent, hip dropped, classical",
    "Leaning back on a railing with both arms extended behind, chest open, looking up at the sky",
    "One hand pulling at the neckline of her sweater, exposing the collarbone, eyes on the camera",
    "Sitting with legs extended, leaning back on both hands, hair falling back, face to the sun",
    "Standing with arms crossed, one hand gripping the opposite elbow, chin lifted, defiant and confident",
    "One leg up on a step, elbow resting on the raised knee, hand supporting her chin, pensive",
    "Back arched, hands on lower back, stretching, head tipped back, silhouette against the light",
    "Sitting on the edge of a surface, legs dangling, one foot bouncing, looking off into the distance",
    "Standing with hands clasped behind her back, chest forward, chin down, quiet authority",
    "Crouching low with one knee on the ground, the other leg extended, hand on the ground for balance",
    "Standing sideways, one arm raised to touch her own neck, head tilted, vulnerable and elegant",
    "Sitting on the floor cross-legged, hands on knees, palms up, meditative and grounded",
    "Standing with hands on her own shoulders, gripping the fabric, as if cold or self-comforting",
    "One hand behind her head, fingers laced in her hair, elbow out, unguarded and relaxed",

    # ── Interactive with environment (51-70) ───────────────────────────────────
    "Leaning against a lamppost, one arm draped over it, hip cocked, old-Hollywood casual",
    "Sitting on a windowsill, legs dangling outside, back against the frame, looking out",
    "Touching her reflection in a mirror or window, fingertips on glass, wistful and self-reflective",
    "Standing in a doorway, one hand on the frame, half in shadow, half in light, threshold moment",
    "Climbing over a low fence or barrier, one leg over, hands gripping the top, mischievous",
    "Sitting on a park bench, leaning forward with elbows on knees, engaged in conversation we can't hear",
    "Pressing her face against a shop window, hands cupped around her eyes, looking in with desire",
    "Standing under an umbrella, one hand holding it, the other reaching out to catch raindrops",
    "Leaning over a bridge railing, looking down at the water, hair hanging forward, contemplative",
    "Sitting on steps, knees up, book or phone in hand, completely absorbed, world passing by",
    "Standing in a phone booth or narrow space, pressed against the glass, cramped and editorial",
    "Walking through a curtain of beads or fabric, parting it with both hands, emerging into light",
    "Lying on grass or a blanket, one arm behind her head, the other trailing daisies or flowers",
    "Standing in a fountain or shallow water, shoes in hand, trousers rolled, laughing at the cold",
    "Climbing a tree, one foot on a branch, hands gripping bark, looking down at the camera",
    "Sitting on a swing, feet kicking out, hair flying back, the chain visible, motion and freedom",
    "Standing in front of a painting or mural, mimicking the pose in the artwork, playful and meta",
    "Kneeling to pet a street cat or dog, head bowed toward the animal, gentle and unaware of camera",
    "Standing in a narrow alley, one shoulder against each wall, arms crossed, filling the space",
    "Walking through fallen leaves or snow, kicking them up with each step, looking back at the trail",

    # ── Facial expression + gaze (71-85) ───────────────────────────────────────
    "Looking directly into the lens with a slow, knowing smile, one eyebrow slightly raised, daring",
    "Eyes closed, head tilted back, lips slightly parted, savoring a moment of pure calm",
    "Staring past the camera into the middle distance, expression unreadable, mysterious and aloof",
    "Biting her lower lip, eyes wide, caught between laughter and surprise, mid-emotion transition",
    "Looking down at her hands, hair falling forward like a curtain, face half-hidden, intimate",
    "Glancing sideways at the camera as if she just noticed it, eyebrow raised, half-smile forming",
    "Laughing with her entire face — eyes crinkled, nose scrunched, mouth wide open, head thrown back",
    "Winking with one eye while sticking her tongue out, playful and irreverent, breaking the fourth wall",
    "Serious and still, chin resting on her folded hands, gaze unwavering, intense and confrontational",
    "Looking over her shoulder with a soft smile, hair falling across one eye, gentle and inviting",
    "Caught between expressions — half-smile fading into thought, eyes losing focus, transitional and real",
    "Staring into the lens without blinking, unsmiling, chin slightly down, eyes up, predatory and captivating",
    "Smiling with closed lips, one corner higher than the other, asymmetric and knowing, Mona Lisa energy",
    "Laughing silently, eyes bright, hand half-raised as if to wave, caught at the exact moment of joy",
    "Expression of pure wonder — eyes wide, mouth slightly open, looking at something off-camera in awe",

    # ── Hands / gestures (86-100) ──────────────────────────────────────────────
    "Both hands framing her own face, fingers spread, peering through her own fingers at the camera",
    "One hand extended toward the camera as if to stop it, palm out, the other hand on her hip",
    "Hands in her hair, pulling it up and away from her face, eyes closed, the motion of washing or wind",
    "Tracing the rim of a glass with one finger, the other hand under her chin, watching the gesture",
    "One hand on her own throat, fingers spread, head tilted, vulnerable and editorial",
    "Both hands gripping the straps of her bag, knuckles visible, shoulders tense, caught in transit",
    "One hand pressing against a wall behind her, fingers spread, leaning back, weight on the palm",
    "Hands clasped in front of her chest as if in prayer or anticipation, eyes closed, solemn",
    "One hand pulling at the collar of her shirt, the other hand in her pocket, casual tension",
    "Fingers interlaced behind her head, elbows out, full-body stretch, unselfconscious and open",
    "One hand shielding her eyes from the sun, the other holding something small — keys, a phone",
    "Both hands wrapped around a cup, steam rising, thumbs overlapping, the warmth visible in her grip",
    "One hand touching a wall or surface, fingers trailing along it as she walks, feeling the texture",
    "Holding a flower or leaf up to the light, examining it, backlit, the veins visible through the petals",
    "Both hands on her own cheeks, palms flat, pushing her face slightly, playful and distorted",
]


# ═══════════════════════════════════════════════════════════════════════════════
# WARDROBE CONSISTENCY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

# When describing wardrobe for carousel mode, append these specificity tags
# to prevent the model from changing the outfit between slides.

WARDROBE_LOCK_SUFFIX = (
    "exact same outfit in every image, same neckline, same fabric, same color, "
    "same cut, same fit, same accessories — do not alter the clothing between shots"
)

HAIR_LOCK_SUFFIX = (
    "same hairstyle with only minor natural variation — strands may shift but the "
    "overall style, color, and length must remain identical across all images"
)