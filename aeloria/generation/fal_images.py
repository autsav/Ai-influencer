import os

import fal_client
import httpx
from pydantic import BaseModel

from aeloria.config import Settings, get_settings
from aeloria.generation.fal_router import WorkflowType, build_payload
from aeloria.generation.post_processor import process_and_save

FLUX_GENERAL_COST_USD = 0.05  # fal-ai/flux-general ~$0.075/MP; verify against pricing

_ASPECT_TO_SIZE = {
    "9:16": "portrait_16_9",
    "4:5": "portrait_4_3",
    "1:1": "square_hd",
    "16:9": "landscape_16_9",
}


class GenerationError(Exception):
    pass


class ImageResult(BaseModel):
    image_bytes: bytes
    cost_usd: float
    gen_params: dict


def _subscribe_and_fetch(model: str, arguments: dict) -> ImageResult:
    """Run the fal endpoint and download the first image. Shared by the default
    and the workflow-routed paths."""
    try:
        result = fal_client.subscribe(model, arguments=arguments)
    except Exception as e:
        raise GenerationError(f"fal generation failed: {e}") from e
    images = result.get("images") or []
    if not images:
        raise GenerationError(f"fal returned no images: {result}")
    resp = httpx.get(images[0]["url"], timeout=60)
    resp.raise_for_status()
    return ImageResult(
        image_bytes=resp.content,
        cost_usd=FLUX_GENERAL_COST_USD,
        gen_params={"model": model, **arguments},
    )


def generate_image(
    prompt: str,
    settings: Settings | None = None,
    aspect_ratio: str = "9:16",
    seed: int | None = None,
    guidance_scale: float | None = None,
    extra_loras: list[dict] | None = None,
    workflow: WorkflowType | None = None,
) -> ImageResult:
    s = settings or get_settings()
    if not s.aeloria_lora_url:
        raise GenerationError("AELORIA_LORA_URL not set — run scripts/train_lora.py first")

    os.environ["FAL_KEY"] = s.fal_key

    # PRO_PHOTOGRAPHY: save original prompt for post-processing film-stock detection
    # (build_payload internally calls cleanse_prompt which modifies the prompt)
    original_prompt = prompt

    # Workflow-routed path: the fal_router builds the endpoint + arguments. LoRA
    # workflows keep the configured (tested) base model via base_model=.
    if workflow is not None:
        lora_wf = workflow in (WorkflowType.IDENTITY_LOCKED_LORA, WorkflowType.OUT_OF_BOX_PHOTOREAL)
        # LoRA workflows: source scales/steps from live config so the tuning knobs
        # (aeloria_lora_scale, realism_lora_scale, guidance, steps) still govern.
        overrides = None
        if lora_wf:
            overrides = {
                "identity_lora_scale": s.aeloria_lora_scale,
                "realism_lora_scale": s.realism_lora_scale,
                "guidance_scale": s.image_guidance_scale,
                "steps": s.image_inference_steps,
            }
        endpoint, arguments = build_payload(
            workflow, prompt,
            identity_lora_url=s.aeloria_lora_url,
            realism_lora_url=(s.realism_lora_url or None),
            seed=seed,
            image_size=_ASPECT_TO_SIZE.get(aspect_ratio, "portrait_16_9"),
            base_model=(s.image_model if lora_wf else None),
            overrides=overrides,
        )
        if guidance_scale is not None:
            arguments["guidance_scale"] = guidance_scale
        if extra_loras and "loras" in arguments:
            arguments["loras"].extend(extra_loras)
        result = _subscribe_and_fetch(endpoint, arguments)

        # PRO_PHOTOGRAPHY: run full post-processing pipeline (WB, sharpen, grain, vignette)
        if workflow == WorkflowType.PRO_PHOTOGRAPHY:
            processed = process_and_save(result.image_bytes, prompt=original_prompt)
            assert isinstance(processed, bytes), "process_and_save(output_dir=None) must return bytes"
            result.image_bytes = processed

        return result

    model = s.image_model
    gs = guidance_scale if guidance_scale is not None else s.image_guidance_scale
    # Identity LoRA first (below 1.0 → less plastic over-fit); extra_loras (skin/
    # realism) append beneath. Juggernaut/flux-lora accept up to 3.
    loras = [{"path": s.aeloria_lora_url, "scale": s.aeloria_lora_scale}]
    if extra_loras:
        loras.extend(extra_loras)
    arguments = {
        "prompt": prompt,
        "loras": loras,
        "guidance_scale": gs,  # < flux default 3.5 → less over-polish / rim light
        "num_inference_steps": s.image_inference_steps,
        "image_size": _ASPECT_TO_SIZE.get(aspect_ratio, "portrait_16_9"),
        "num_images": 1,
    }
    if seed is not None:
        arguments["seed"] = seed

    # IP-Adapter reference conditioning — only fal-ai/flux-general supports the
    # ip_adapters param; Juggernaut does not (identity rests on the scale-1.0
    # LoRA). Empty ref url = kill switch.
    if s.ip_adapter_ref_image_url and model == "fal-ai/flux-general":
        arguments["ip_adapters"] = [{
            "path": s.ip_adapter_path,
            "image_encoder_path": s.ip_adapter_image_encoder_path,
            "image_url": s.ip_adapter_ref_image_url,
            "scale": s.ip_adapter_scale,
        }]

    return _subscribe_and_fetch(model, arguments)
