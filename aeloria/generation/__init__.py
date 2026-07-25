# Generation Module — Boundary Rules
# ============================================================
#
# This module is SOUL 2.0 PURPOSES ONLY.
#
# RULE: No backstory, lore, world-building, or narrative content
# may enter this module. The generation pipeline is a pure function:
#
#   brief (mood, location, wardrobe, camera) + visual_dna + lora → image
#
# Identity is carried SOLELY by the LoRA. All text in prompts is
# physical-descriptor only (hair, eyes, skin, age, body type).
#
# ============================================================
# WHAT LIVES HERE (allowed)
# ============================================================
#   prompt_builder.py   — physical-descriptor prompt assembly
#   fal_images.py       — FAL AI image generation with LoRA
#   fal_video.py        — FAL AI video generation
#   face_gate.py       — InsightFace identity verification
#   edit.py            — FAL flux-kontext inpainting
#   worker.py           — orchestration: brief → image → verify
#   video_worker.py     — frame extraction + video post
#   realism_injector.py — anti-plastic negative prompt module
#   presets.py          — mood/camera/style preset catalogue
#
# ============================================================
# WHAT DOES NOT LIVE HERE (forbidden)
# ============================================================
#   persona/backstory.yaml
#   persona/loader.py (has backstory logic — use load_persona() only)
#   caption.py (narrative layer, belongs in content/)
#   showrunner/  (narrative planning, belongs in social/)
#   engagement/  (DM/inbound logic, belongs in social/)
#
# If you need backstory context for a generation, it must come from
# a USER-PROVIDED brief override. It is never embedded in code here.
#
# Test contract: tests/test_prompt_builder.py enforces zero
# backstory keywords in assembled prompts.
