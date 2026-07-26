# Aeloria Prompt Architect — Flux Image Generation Expert Guide

## Model & Pipeline Context

| Parameter | Value |
|-----------|-------|
| Model | `rundiffusion-fal/juggernaut-flux-lora` |
| LoRA | Aeloria face LoRA, scale 0.7 |
| Guidance | 3.5 |
| Steps | 40 |
| Aspect ratio | 4:5 (→ 896×1152px, internally `portrait_16_9`) |
| Negative prompt | **NOT SUPPORTED** — Flux has no native negative prompt slot |

**Critical:** Because Flux lacks negative prompts, every anti-pattern (plastic skin, extra limbs, wrong identity) must be prevented through positive-only framing. What you don't say, you don't get.

---

## The 10-Layer Prompt Structure

Every prompt is a **natural-language paragraph** (not tag list), built in this order:

```
1. SHOT TYPE + AESTHETIC       → "A candid fashion photograph"
2. SUBJECT IDENTITY             → LoRA trigger + Visual DNA (face, hair, eyes, skin)
3. WARDROBE                    → Clothing with fabric, fit, neckline, texture detail
4. POSE                        → Explicit body positioning + hand placement
5. ENVIRONMENT                 → Location, atmosphere, time, weather, mood
6. CAMERA ANGLE                → Lens, aperture, composition, lighting direction
7. TECHNICAL PROFILE           → Film stock, shutter speed, lighting modifiers
8. SKIN REALISM BLOCK          → Anti-plastic skin details (pores, freckles, peach fuzz)
9. IDENTITY LOCK               → Preserve Aeloria's face/hair/body exactly
10. FINAL GUARD                → Film grain, anatomy guard, quality tags
```

### Layer 1 — Shot Type + Aesthetic
Always start with: `A candid fashion photograph`

This sets editorial context and reduces Flux's tendency to generate studio-portrait or glamour-shot aesthetics.

### Layer 2 — Subject Identity
```
aeloria woman, auburn hair in a loose messy bun with flyaway strands framing her face, green eyes, fair skin with freckles across nose and cheeks, visible pores, peach fuzz
```
**LoRA trigger is `aeloria woman`** — this must be the first words after the shot type. Never vary this phrase.

**Visual DNA** comes from `aeloria/persona/aeloria.yaml`:
- `visual_dna.hair`: auburn, usually in a loose messy bun, loose pieces framing her face
- `visual_dna.eyes`: green
- `visual_dna.skin`: fair with freckles across nose and cheeks, visible pores, peach fuzz on upper lip and forehead

### Layer 3 — Wardrobe
Must include **neckline type** explicitly — Flux drifts clothing without it.
```
wearing [item], [fabric], [neckline/collar type], [fit description], [how it catches light]
```
Examples:
- `wearing a charcoal crew-neck t-shirt under a navy structured overshirt, clean white sneakers, gold hoop earrings`
- `wearing an olive green henley with rolled sleeves, dark denim jeans, minimal leather sneakers, gold hoop earrings`

**Wardrobe style:** Smart casual. Neutral colours — charcoal, navy, olive, cream, warm grey. Never overly formal. Never overly luxurious. The brand communicates: "She's successful because she's smart, not because she's showing off."

**If no neckline specified:** pipeline auto-appends `, fitted silhouette following her body shape` — but explicit is always better.

**Clothing drift prevention:** When reusing an outfit across a carousel, copy-paste the exact wardrobe string. Never paraphrase.

### Layer 4 — Pose
**Explicit hand positioning is mandatory.** Flux's #1 failure mode is extra or malformed hands.

Anti-pattern: `smiling happily` → Flux may generate 6 fingers.
Safe pattern: `one hand on the keyboard, the other holding a coffee mug, five fingers visible on each hand`

Pose should describe: chin position, gaze direction, weight distribution, arm positions, expression.

### Layer 5 — Environment
Plain prose. Include atmosphere, time of day, weather, lighting quality, mood.
```
working at a clean white desk in a minimal home office, MacBook open showing a workflow diagram, warm desk lamp, one plant, morning light through the window
```

### Layer 6 — Camera Angle
Photography composition terms:
- `eye-level 50mm, shallow depth of field` — standard portrait
- `over-the-shoulder from behind the laptop, screen visible` — work shot
- `low-angle 85mm telephoto looking slightly up at her against the city` — dramatic
- `candid wide shot from across the café, natural and unstaged` — lifestyle

### Layer 7 — Technical Profile
Photography modifiers that control final look:
- `Shot on Kodak Portra 400, 50mm lens at f/2.0, natural depth of field` — warm, natural
- `Clean digital capture, 35mm lens, natural window light, sharp and modern` — clean tech
- `Point-and-shoot hard flash, direct on-camera flash, 1/125s, f/8, ISO 400` — punchy candid
- `Under-exposed shadow priority, exposure bias -1.0 to -1.5 EV, dark moody shadows` — moody

### Layer 8 — Skin Realism Block
This is the anti-plastic layer. Always include:
```
Raw authentic skin with visible pores across the cheeks and nose, faint freckles, subtle natural redness around the nose, tiny skin bumps, fine peach fuzz catching the light, soft natural oil highlights on the nose and forehead — no smoothing, no beauty filter
```

### Layer 9 — Identity Lock
```
Preserve aeloria's exact identity — same face, auburn hair and the same recognizable person in every image. Do NOT change facial features or body shape.
```

### Layer 10 — Final Guard
```
subtle film grain, raw unretouched editorial look, natural lighting. Two hands only, correct anatomy, five fingers on each hand
```

---

## Converting a User Prompt → Pipeline Prompt

When the user pastes a normal prompt, expand it through this filter:

### Input Analysis
Read the user's raw prompt and extract:
- **Who** → Always `aeloria woman` + Visual DNA
- **What scene** → Extract location, time, atmosphere, weather
- **What wardrobe** → Clothing items, fabrics, accessories (add neckline if missing)
- **What pose** → Body position, hand positions (add explicit hands if missing)
- **What camera** → Lens, angle, composition (or leave for auto-select)

### Expansion Rules

| Missing Element | Auto-Append |
|---------------|-------------|
| No neckline in wardrobe | `, fitted silhouette following her body shape` |
| No hand description in pose | `, both hands visible and naturally positioned` |
| No tech profile | `Shot on Kodak Portra 400, 50mm lens at f/2.0, natural depth of field` |
| No skin realism | Full skin realism block from character.json |
| No identity lock | Identity lock from character.json |

### Example Conversion

**User input:**
```
"aeloria working in a coffee shop on an AI workflow"
```

**Expanded:**
```
A candid fashion photograph. aeloria woman, auburn hair in a loose messy bun with flyaway strands framing her face, green eyes, fair skin with freckles across nose and cheeks, visible pores, peach fuzz. wearing a charcoal crew-neck t-shirt under a navy structured overshirt, clean white sneakers, gold hoop earrings. working at a café corner table, MacBook open showing a workflow, flat white beside it, natural light through the window. Shot on Kodak Portra 400, 50mm lens at f/2.0, natural depth of field. Raw authentic skin with visible pores across the cheeks and nose, faint freckles, subtle natural redness around the nose, tiny skin bumps, fine peach fuzz catching the light, soft natural oil highlights on the nose and forehead — no smoothing, no beauty filter. Preserve aeloria's exact identity — same face, auburn hair and the same recognizable person in every image. Do NOT change facial features or body shape. subtle film grain, raw unretouched editorial look, natural lighting. Two hands only, correct anatomy, five fingers on each hand.
```

---

## Flux-Specific Rules (What NOT To Do)

1. **Never use negative prompts** — `!distorted, !blurry` doesn't work on Flux. Use positive framing only.
2. **Never use tag lists** — `masterpiece, best quality, amazing` degrades Flux. Write prose.
3. **Never omit neckline** — Flux will invent a neckline that contradicts your outfit description.
4. **Never leave hands vague** — `smiling` → Flux may add fingers. Be explicit: `right hand on the keyboard, left hand holding a coffee mug`.
5. **Never vary the LoRA trigger** — Always `aeloria woman`. Never `a woman named Aeloria`, never `character Aeloria`.
6. **Never use "photo of"** — Use `candid fashion photograph` as your opener. "Photo of" triggers Flux's training aesthetics.

---

## Carousel Continuity Rules

When generating a carousel (multiple slides of the same outfit/character):

1. **Copy the exact wardrobe string** across all slides — do not paraphrase
2. **Only vary**: pose, camera angle, lighting direction, background detail
3. **Keep the same scene type**: all indoor OR all outdoor, same time of day
4. **Reuse the same seed** if you need pixel-perfect identity consistency (seed locks everything including noise pattern)
5. **Change seed** for creative variation; Aeloria's face will still be preserved via LoRA

---

## Output Specs

| Field | Value |
|-------|-------|
| Resolution | 896×1152 (4:5 portrait) |
| Format | PNG |
| File size | < 20MB |
| Face similarity threshold | ≥ 0.35 (InsightFace cosine) |
| Min dimensions | 512×512 |

---

## Quick Reference: Prompt Builder Function Signature

```python
build_prompt(
    persona: Persona,        # loaded from aeloria.yaml
    brief: dict,              # {prompt_seed, wardrobe?, pillar?, mood?, location?, ...}
) -> str
```

The function auto-fills missing wardrobe and missing hand descriptions before building. The runner auto-selects pose/camera/tech if not provided.