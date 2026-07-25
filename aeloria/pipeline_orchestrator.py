"""
End-to-end orchestrator — runs the full AI Influencer Pipeline.

Stage 1: Persona & Character Consistency (LoRA + realistic prompt engine)
Stage 2: Content Generation (trend scraper + hook generation + caption)
Stage 3: Visual Generation (FAL Flux + LoRA → post-process)
Stage 4: Audio & Lip-Sync (voice clone → lip-sync)
Stage 5: Rendering & Publishing (FFmpeg → C2PA → publish)

Usage:
    from aeloria.pipeline_orchestrator import run_full_pipeline
    result = run_full_pipeline("Aeloria at a London café, morning light")
"""
from __future__ import annotations

import os
import time
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PIL import Image


@dataclass
class PipelineResult:
    image_path: str = ""
    image_bytes: bytes = b""
    caption: str = ""
    hooks: list[str] = field(default_factory=list)
    audio_path: str = ""
    video_path: str = ""
    subtitle_path: str = ""
    cost_usd: float = 0.0
    stages_completed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_full_pipeline(
    scene: str,
    wardrobe: str = "",
    generate_voice_narration: bool = False,
    generate_video: bool = False,
    seed: int | None = None,
) -> PipelineResult:
    """
    Run the full 5-stage AI Influencer Pipeline for a single post.
    
    Args:
        scene: Scene description (e.g. "sitting at a London café, morning light")
        wardrobe: Optional wardrobe override
        generate_voice: Whether to generate voice narration (requires ElevenLabs/XTTS)
        generate_video: Whether to render a video (requires FFmpeg + image)
        seed: Random seed for reproducibility
    
    Returns:
        PipelineResult with all generated assets
    """
    import random
    rng_seed = seed or random.randint(0, 2**32)
    result = PipelineResult()
    
    # ── Stage 1: Persona & Prompt ─────────────────────────────────────────────
    print("\n{'='*60}")
    print("  STAGE 1: Persona & Realistic Prompt Engine")
    print("{'='*60}")
    
    try:
        from aeloria.generation.realistic_prompt_engine import build_realistic_prompt
        positive, negative = build_realistic_prompt(scene, wardrobe=wardrobe, seed=rng_seed)
        result.stages_completed.append("stage1_prompt")
        print(f"  ✅ Prompt built ({len(positive)} chars)")
    except Exception as e:
        result.errors.append(f"Stage 1 failed: {e}")
        print(f"  ❌ Stage 1 failed: {e}")
        return result
    
    # ── Stage 2: Content Generation (Caption + Hooks) ─────────────────────────
    print("\n{'='*60}")
    print("  STAGE 2: Content Generation")
    print("{'='*60}")
    
    try:
        from aeloria.generation.trend_scraper import generate_hooks
        from aeloria.llm_router import llm_generate
        
        # Generate hooks
        hooks = generate_hooks(scene, count=3)
        result.hooks = hooks
        print(f"  ✅ Generated {len(hooks)} hooks")
        
        # Generate caption
        caption_prompt = f"""Write a 3-line Instagram caption for an image of: {scene}

Rules:
- First line is a punchy hook (not a question)
- Second line is a dry observation
- Third line is a subtle call-to-action
- No hashtags in the caption
- Keep it under 150 characters total
- Tone: warm, grounded, slightly poetic

Caption:"""
        
        result.caption = llm_generate(caption_prompt, timeout=30)
        result.stages_completed.append("stage2_content")
        print(f"  ✅ Caption: {result.caption[:80]}...")
        
    except Exception as e:
        result.errors.append(f"Stage 2 failed: {e}")
        print(f"  ⚠️ Stage 2 failed: {e} — continuing")
    
    # ── Stage 3: Visual Generation ────────────────────────────────────────────
    print("\n{'='*60}")
    print("  STAGE 3: Visual Generation")
    print("{'='*60}")
    
    try:
        import fal_client
        import httpx
        from aeloria.config import get_settings
        from aeloria.generation.post_processor import (
            auto_wb_exposure, selective_sharpen, film_grain, vignette
        )
        
        s = get_settings()
        os.environ["FAL_KEY"] = s.fal_key
        
        arguments = {
            "prompt": positive,
            "guidance_scale": 3.5,
            "num_inference_steps": 40,
            "image_size": "portrait_16_9",
            "seed": rng_seed,
            "loras": [{"path": s.aeloria_lora_url, "scale": s.aeloria_lora_scale}],
            "num_images": 1,
            "enable_safety_checker": False,
        }
        
        print("  Generating image via FAL Flux...")
        t0 = time.time()
        fal_result = fal_client.subscribe("fal-ai/flux-lora", arguments=arguments)
        img_url = fal_result["images"][0]["url"]
        img_data = httpx.get(img_url, timeout=300).content
        print(f"  ✅ Image generated in {time.time()-t0:.1f}s ({len(img_data)//1024} KB)")
        
        # Post-process
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        img = auto_wb_exposure(img, strength=0.35)
        img = selective_sharpen(img, amount=1.2, radius=0.8, threshold=3)
        img = film_grain(img, intensity=0.10)
        img = vignette(img, strength=0.15)
        
        result.image_path = "/tmp/aeloria_pipeline_output.jpg"
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=95)
        result.image_bytes = out.getvalue()
        
        with open(result.image_path, "wb") as f:
            f.write(result.image_bytes)
        
        result.cost_usd = 0.05
        result.stages_completed.append("stage3_visual")
        print(f"  ✅ Post-processed and saved")
        
    except Exception as e:
        result.errors.append(f"Stage 3 failed: {e}")
        print(f"  ❌ Stage 3 failed: {e}")
        return result
    
    # ── Stage 4: Audio & Lip-Sync (optional) ───────────────────────────────────
    if generate_voice_narration and result.caption:
        print("\n{'='*60}")
        print("  STAGE 4: Audio & Lip-Sync")
        print("{'='*60}")
        
        try:
            from aeloria.generation.audio_pipeline import generate_voice as gen_voice, generate_srt_subtitles
            
            result.audio_path = gen_voice(result.caption, output_path="/tmp/aeloria_voice.mp3")
            result.subtitle_path = generate_srt_subtitles(result.caption, 5.0, "/tmp/aeloria_subtitles.srt")
            result.stages_completed.append("stage4_audio")
            print(f"  ✅ Voice + subtitles generated")
        except Exception as e:
            result.errors.append(f"Stage 4 failed: {e}")
            print(f"  ⚠️ Stage 4 skipped: {e}")
    
    # ── Stage 5: Rendering & Publishing ───────────────────────────────────────
    if generate_video:
        print("\n{'='*60}")
        print("  STAGE 5: Rendering")
        print("{'='*60}")
        
        try:
            from aeloria.generation.render_pipeline import render_image_to_video, RenderConfig
            
            cfg = RenderConfig(width=1080, height=1920, fps=30, preset="fast")
            result.video_path = render_image_to_video(
                image_path=result.image_path,
                audio_path=result.audio_path if result.audio_path else None,
                subtitle_path=result.subtitle_path if result.subtitle_path else None,
                duration=5.0,
                output_path="/tmp/aeloria_pipeline_video.mp4",
                config=cfg,
            )
            result.stages_completed.append("stage5_render")
            print(f"  ✅ Video rendered")
        except Exception as e:
            result.errors.append(f"Stage 5 failed: {e}")
            print(f"  ⚠️ Stage 5 skipped: {e}")
    
    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  PIPELINE COMPLETE")
    print("="*60)
    print(f"  Stages completed: {', '.join(result.stages_completed)}")
    print(f"  Cost: ${result.cost_usd:.2f}")
    if result.errors:
        print(f"  Warnings: {len(result.errors)}")
        for e in result.errors:
            print(f"    ⚠️ {e}")
    print(f"  Image: {len(result.image_bytes)//1024} KB")
    if result.video_path:
        print(f"  Video: {os.path.getsize(result.video_path)/1e6:.1f} MB")
    
    return result