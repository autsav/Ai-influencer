"""Carousel generation: N slide images from one brief's prompt_seed, each with
its own overlay text. Reuses the fal LoRA + face gate per slide. First-slide
gate failure aborts (no partial publish). $0.05/slide via check_budget."""
import logging

from aeloria.budget import check_budget
from aeloria.generation.face_gate import FaceGateError, passes_gate
from aeloria.generation.fal_images import FLUX_GENERAL_COST_USD, generate_image
from aeloria.generation.fal_router import resolve_workflow
from aeloria.generation.post import overlay_image_text
from aeloria.generation.prompt_builder import build_prompt
from aeloria.generation.refine import refine_and_regate

log = logging.getLogger(__name__)


def carousel_slide_texts(brief: dict, max_slides: int, default_slides: int) -> list[str]:
    """Overlay text per slide, from distribution_plan.on_screen_keywords.
    Clamped to [2, max_slides]. When no keywords, `default_slides` empty overlays."""
    kws = (brief.get("distribution_plan") or {}).get("on_screen_keywords") or []
    if not kws:
        return [""] * default_slides
    slides = kws[:max_slides]
    if len(slides) < 2:
        slides = slides + [""] * (2 - len(slides))
    return slides


def generate_carousel(brief, db, settings, r2, persona, ref_embedding) -> list[dict]:
    """Return one media_assets dict per slide (image kind), in slide order.
    First-slide face-gate failure -> [] (caller marks the brief failed)."""
    prompt = build_prompt(persona, brief)
    slides = carousel_slide_texts(brief, settings.carousel_max_slides, settings.carousel_default_slides)
    # Route via the brief's workflow (router stacks realism); legacy briefs use
    # the default path with realism passed as extra_loras.
    wf = resolve_workflow(brief)
    extra_loras = None
    if wf is None and settings.realism_lora_url:
        extra_loras = [{"path": settings.realism_lora_url, "scale": settings.realism_lora_scale}]

    assets: list[dict] = []
    for i, text in enumerate(slides):
        check_budget(db, settings, "fal", FLUX_GENERAL_COST_USD)
        result = generate_image(
            f"{prompt} (carousel slide {i + 1})",
            settings=settings, aspect_ratio="4:5", workflow=wf, extra_loras=extra_loras,
        )
        try:
            sim, ok = passes_gate(result.image_bytes, ref_embedding, settings.face_gate_threshold)
        except FaceGateError:
            sim, ok = None, False
        # Cost row before post-processing so failed overlay/upload still tracks spend.
        asset = db.insert("media_assets", {
            "brief_id": brief["id"], "r2_url": None, "kind": "image",
            "engine": "fal", "gen_params": result.gen_params,
            "cost": result.cost_usd, "face_similarity": sim,
        })
        if not ok:
            if i == 0:
                log.warning("carousel %s: first slide failed face gate, aborting", brief["id"])
                return []
            log.warning("carousel %s: slide %d failed gate, stopping at %d slides",
                        brief["id"], i, len(assets))
            break
        slide_bytes, _ = refine_and_regate(result.image_bytes, settings, ref_embedding, sim)
        img = overlay_image_text(slide_bytes, text, settings) if text else slide_bytes
        key = f"content/{brief['slot_day']}/{brief['id']}-c{i}.png"
        url = r2.upload(img, key, "image/png")
        db.update("media_assets", asset["id"], {"r2_url": url})
        assets.append({**asset, "r2_url": url})
    return assets
