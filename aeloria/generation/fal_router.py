"""fal.ai payload router (Python port of src/services/falRouter.ts).

Pure payload construction: `build_payload` returns `(endpoint, arguments)` for a
`WorkflowType`; the actual call is `fal_client.subscribe(endpoint, arguments)` in
`fal_images.generate_image`. Baselines mirror the tuned Python config (identity
0.78, realism 0.45, guidance 1.9). No network I/O here.
"""
import re
from enum import Enum


class WorkflowType(str, Enum):
    """Generation/edit workflows, each mapped to a fal endpoint."""
    IDENTITY_LOCKED_LORA = "IDENTITY_LOCKED_LORA"   # custom identity + realism LoRA
    OUT_OF_BOX_PHOTOREAL = "OUT_OF_BOX_PHOTOREAL"   # juggernaut, single identity LoRA
    IN_PAINTING_EDIT = "IN_PAINTING_EDIT"           # flux-kontext instruction edit
    MULTI_REF_BLEND = "MULTI_REF_BLEND"             # nano-banana multi-reference
    HIGH_RES_EDITORIAL = "HIGH_RES_EDITORIAL"       # flux-pro ultra high-res stills
    PRO_PHOTOGRAPHY     = "PRO_PHOTOGRAPHY"         # flux-pro + explicit photography direction


# endpoint + baseline params per workflow.
WORKFLOW_MODELS: dict[WorkflowType, dict] = {
    WorkflowType.IDENTITY_LOCKED_LORA: {
        "endpoint": "fal-ai/flux-lora",
        "defaults": {"identity_lora_scale": 0.78, "realism_lora_scale": 0.45,
                     "guidance_scale": 1.9, "steps": 30},
    },
    WorkflowType.OUT_OF_BOX_PHOTOREAL: {
        "endpoint": "rundiffusion-fal/juggernaut-flux-lora",
        "defaults": {"identity_lora_scale": 0.74, "guidance_scale": 1.9, "steps": 30},
    },
    WorkflowType.IN_PAINTING_EDIT: {
        "endpoint": "fal-ai/flux-kontext/dev",
        "defaults": {"guidance_scale": 3.5, "steps": 28},
    },
    WorkflowType.MULTI_REF_BLEND: {
        "endpoint": "fal-ai/nano-banana-pro",
        "defaults": {"aspect_ratio": "9:16"},
    },
    WorkflowType.HIGH_RES_EDITORIAL: {
        "endpoint": "fal-ai/flux-pro/v1.1-ultra",
        "defaults": {"raw": True, "aspect_ratio": "9:16"},
    },
    WorkflowType.PRO_PHOTOGRAPHY: {
        # flux-pro 1.1 ultra — the highest-fidelity portrait model FAL offers.
        # Keep raw=False so FAL's built-in colour science applies.
        "endpoint": "fal-ai/flux-pro/v1.1-ultra",
        "defaults": {"raw": False, "aspect_ratio": "9:16"},
    },
}

# ── Surgical prompt cleanser ─────────────────────────────────────────────────
# Removes only genuinely-harmful AI buzzwords.
# KEEPS all legitimate professional photography vocabulary:
#   lens mm values, f-stops, bokeh, depth of field, named film stocks,
#   specific lighting terms (rim light, butterfly, Rembrandt), color grades.
#
# Why: Juggernaut was trained on millions of professional photos.
# Feeding it "85mm f/1.4, Kodak Portra 800, rim light from camera left,
# shallow bokeh" dramatically shifts output quality vs generic prompts.
#
# What we REMOVE:
#   - resolution lies:   4k, 8k (upscaler territory, not generation)
#   - quality signals:  masterpiece, best quality, perfect anatomy,
#                        perfect face, dreamlike, ethereal, otherworldly
#   - AI fingerprints:  hyperrealistic, ultrarealistic, photorealistic
#                        (model collapses to training average)
#   - generic vagueness: cinematic (any variant), cinematic lighting,
#                        dramatic lighting, movie still
# What we KEEP (do NOT add to _BANNED):
#   - specific lens:    85mm, 50mm, 35mm, 24mm + f/1.4, f/2.8, etc.
#   - depth/bokeh:      shallow depth of field, creamy bokeh, subject sharp
#   - film stocks:      Kodak Portra 400/800, Cinestill 800T, Fuji Pro 400H
#   - lighting rigs:    rim light, butterfly, Rembrandt, split, loop,
#                       golden hour, blue hour, hard light, soft box
#   - color/grain:      warm grade, cool grade, film grain, halation

_BANNED = [
    # Resolution inflation
    re.compile(r"\b[48]k\b", re.I),
    re.compile(r"\b6k\b", re.I),
    re.compile(r"\buhd\b", re.I),
    # Quality inflation
    re.compile(r"\bmasterpiece\b", re.I),
    re.compile(r"\bbest quality\b", re.I),
    re.compile(r"\bperfect anatomy\b", re.I),
    re.compile(r"\bperfect face\b", re.I),
    re.compile(r"\bdreamlike\b", re.I),
    re.compile(r"\bethereal\b", re.I),
    re.compile(r"\botherworldly\b", re.I),
    # AI fingerprints (collapse to training average)
    re.compile(r"\bhyper[-\s]?realistic\b", re.I),
    re.compile(r"\bultra[-\s]?realistic\b", re.I),
    re.compile(r"\bphoto[-\s]?realistic\b", re.I),
    # Generic vagueness (model doesn't know what you mean)
    re.compile(r"\bcinematic\b", re.I),
    re.compile(r"\bcinematic lighting\b", re.I),
    re.compile(r"\bdrama(tic)? lighting\b", re.I),
    re.compile(r"\bmovie still\b", re.I),
]

# Fallback camera tokens when buzzwords are stripped and no real photography
# language is present.  This is a FLOOR, not a target — specific terms beat this.
_CAMERA_FALLBACK = "shot on 35mm lens, natural daylight, raw JPEG texture"

_LORA_WORKFLOWS = (WorkflowType.IDENTITY_LOCKED_LORA, WorkflowType.OUT_OF_BOX_PHOTOREAL)


def resolve_workflow(brief: dict) -> "WorkflowType | None":
    """Map a brief's stamped `workflow` string to a WorkflowType, or None for the
    default (config-driven) generation path. Unknown/blank values → None."""
    raw = brief.get("workflow")
    if not raw:
        return None
    try:
        return WorkflowType(raw)
    except ValueError:
        return None


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,(?:\s*,)+", ",", text)     # ", ,"  -> ","
    text = re.sub(r",\s*(?=,)", "", text)
    text = re.sub(r"^[\s,]+|[\s,]+$", "", text)     # trim leading/trailing spaces+commas
    return text.strip()


def cleanse_prompt(raw: str) -> str:
    """Strip only genuinely-harmful AI buzzwords; preserve all legitimate
    professional photography vocabulary (lens mm, f-stops, named film stocks,
    specific lighting terms).  When buzzwords are stripped AND no specific
    photography language is present, append a generic camera realism token
    as a floor.  Idempotent."""
    out = raw
    stripped = False
    for pat in _BANNED:
        nxt = pat.sub("", out)
        if nxt != out:
            stripped = True
            out = nxt
    out = _tidy(out)
    # Specific photography vocabulary — if any is present, keep it and skip fallback
    _HAS_PHOTO_VOCAB = re.search(
        r"\b(85mm|50mm|35mm|24mm|f?/?1\.\d|f/?2\.\d|f/?4|"
        r"kodak|cinestill|fuji|film stock|portra|cinestill|"
        r"bokeh|depth of field|shallow dof|rim light|butterfly|rembrandt|"
        r"golden hour|blue hour|hard light|soft box|"
        r"warm grade|cool grade|film grain|halation)\b",
        out, re.I,
    )
    if stripped and not _HAS_PHOTO_VOCAB:
        out = f"{out}, {_CAMERA_FALLBACK}" if out else _CAMERA_FALLBACK
    return out


def build_payload(
    workflow: WorkflowType,
    prompt: str,
    *,
    identity_lora_url: str | None = None,
    realism_lora_url: str | None = None,
    image_url: str | None = None,
    mask_url: str | None = None,
    reference_image_urls: list[str] | None = None,
    seed: int | None = None,
    overrides: dict | None = None,
    base_model: str | None = None,
    image_size: str | None = None,
    num_images: int = 1,
) -> tuple[str, dict]:
    """Return `(endpoint, arguments)` for a workflow.

    `base_model` overrides the endpoint for the LoRA workflows so the live
    pipeline can keep its configured (tested) base model. Raises on unknown
    workflow or missing required input.
    """
    cfg = WORKFLOW_MODELS.get(workflow)
    if cfg is None:
        raise ValueError(f"Unknown workflow: {workflow}")
    endpoint = base_model or cfg["endpoint"]
    params = {**cfg["defaults"], **(overrides or {})}

    body: dict = {"prompt": cleanse_prompt(prompt)}
    if "guidance_scale" in params:
        body["guidance_scale"] = params["guidance_scale"]
    if "steps" in params:
        body["num_inference_steps"] = params["steps"]
    if params.get("aspect_ratio"):
        body["aspect_ratio"] = params["aspect_ratio"]
    if "raw" in params:
        body["raw"] = params["raw"]
    if image_size:
        body["image_size"] = image_size
    if seed is not None:
        body["seed"] = seed

    if workflow in _LORA_WORKFLOWS:
        loras: list[dict] = []
        if identity_lora_url:
            loras.append({"path": identity_lora_url,
                          "scale": params.get("identity_lora_scale", 0.78)})
        if workflow == WorkflowType.IDENTITY_LOCKED_LORA and realism_lora_url:
            loras.append({"path": realism_lora_url,
                          "scale": params.get("realism_lora_scale", 0.45)})
        body["loras"] = loras
        body["num_images"] = num_images
    elif workflow == WorkflowType.IN_PAINTING_EDIT:
        if not image_url:
            raise ValueError("IN_PAINTING_EDIT requires image_url")
        body["image_url"] = image_url
        if mask_url:
            body["mask_url"] = mask_url
    elif workflow == WorkflowType.MULTI_REF_BLEND:
        body["image_urls"] = reference_image_urls or []
    # HIGH_RES_EDITORIAL: raw + aspect_ratio already applied above.

    return endpoint, body
