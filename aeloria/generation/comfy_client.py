"""
ComfyUI client for local SD1.5 + Aeloria LoRA generation.
Routes /photo through ComfyUI when local model is ready.
"""
import base64
import io
import json
import time
import uuid
from pathlib import Path

import requests
from PIL import Image

COMFY_URL = "http://localhost:8188"
TIMEOUT = 300  # 5 min for generation

# Base SD1.5 workflow — minimal working graph
# Nodes 1-4: Load checkpoint → Encode prompts → Sample → Decode → Save


def build_sdxl_workflow(
    prompt: str,
    negative_prompt: str,
    seed: int,
    steps: int = 25,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    lora_path: str = "",
    lora_strength: float = 0.85,
    width: int = 512,
    height: int = 512,
    ckpt_name: str = "",
) -> dict:
    """
    Build a complete SD1.5 + LoRA ComfyUI workflow.
    
    Args:
        prompt: Positive conditioning text
        negative_prompt: Negative conditioning text
        seed: Random seed for reproducibility
        steps: Number of sampling steps
        cfg: CFG scale
        sampler: Sampler name (euler, euler_ancestral, dpmpp_2m, etc.)
        scheduler: Scheduler (normal, karras, exponential, etc.)
        lora_path: Absolute path to .safetensors LoRA file (empty = no LoRA)
        lora_strength: LoRA strength (0.0-2.0, 0.85 is default)
        width, height: Output resolution
    
    Returns:
        Workflow dict ready for POST /prompt
    """
    workflow_id = str(uuid.uuid4())[:8]
    
    # Sampler name to node class mapping
    sampler_class = sampler  # euler, dpmpp_2m, etc. — passed directly to sampler_name
    
    # Load checkpoint — SD1.5 or SDXL
    workflow = {}
    if "xl" in ckpt_name.lower() or "juggernaut" in ckpt_name.lower():
        workflow["1"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
            }
        }
        if width == 512 and height == 512:
            width, height = 1024, 1024  # SDXL native resolution
    else:
        workflow["1"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {
                "ckpt_name": "v1-5-pruned-emaonly.safetensors"
            }
        }

    # 2: Positive CLIP text encode
    workflow["2"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": prompt,
            "clip": ["1", 1]
        }
    }
    # 3: Negative CLIP text encode
    workflow["3"] = {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": negative_prompt,
            "clip": ["1", 1]
        }
    }
    # 4: Empty latent (canvas size)
    workflow["4"] = {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": width,
            "height": height,
            "batch_size": 1
        }
    }
    
    # Add LoRA loader if path provided
    if lora_path and Path(lora_path).exists():
        lora_name = Path(lora_path).name
        # 5: Lora loader (models/loras/ path inside ComfyUI root)
        workflow["5"] = {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": lora_name,
                "strength_model": lora_strength,
                "strength_clip": lora_strength,
                "model": ["1", 0],   # node 1, output 0 = model
                "clip": ["1", 1]     # node 1, output 1 = CLIP
            }
        }
        model_source = ["5", 0]  # LoRA-modified model
        clip_source = ["5", 1]   # LoRA-modified CLIP
    else:
        model_source = ["1", 0]
        clip_source = ["1", 1]
    
    # Update CLIPTextEncode nodes to use LoRA CLIP
    workflow["2"]["inputs"]["clip"] = clip_source
    workflow["3"]["inputs"]["clip"] = clip_source
    
    # 6: KSampler (always use KSampler — denoise is a required field)
    workflow["6"] = {
        "class_type": "KSampler",
        "inputs": {
            "model": model_source,
            "positive": ["2", 0],
            "negative": ["3", 0],
            "latent_image": ["4", 0],
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler,  # pass full name (euler, euler_ancestral, dpmpp_2m, etc.)
            "scheduler": scheduler,
            "denoise": 1.0,
        }
    }
    
    # 7: VAE decode
    workflow["7"] = {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["6", 0],
            "vae": ["1", 2]  # node 1, output 2 = VAE
        }
    }
    
    # 8: Save image (to temp)
    workflow["8"] = {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": f"aeloria_{workflow_id}",
            "images": ["7", 0]
        }
    }
    
    return workflow


def generate_image_comfy(
    prompt: str,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int = 25,
    cfg: float = 7.0,
    sampler: str = "euler",
    scheduler: str = "normal",
    lora_path: str = "",
    lora_strength: float = 0.85,
    width: int = 512,
    height: int = 512,
    ckpt_name: str = "",
) -> Image.Image:
    """
    Generate an image via ComfyUI (SD1.5 or SDXL).
    
    Returns:
        PIL Image ready for post-processing and delivery.
    
    Raises:
        RuntimeError: If ComfyUI returns an error or times out.
    """
    import random
    
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    if negative_prompt is None:
        negative_prompt = "blurry, low quality, distorted, deformed, ugly, bad anatomy"
    
    workflow = build_sdxl_workflow(
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        steps=steps,
        cfg=cfg,
        sampler=sampler,
        scheduler=scheduler,
        lora_path=lora_path,
        lora_strength=lora_strength,
        width=width,
        height=height,
    )
    
    prompt_id = str(uuid.uuid4())
    
    # Submit workflow
    resp = requests.post(
        f"{COMFY_URL}/prompt",
        json={"prompt": workflow, "prompt_id": prompt_id},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    
    if "error" in data:
        raise RuntimeError(f"ComfyUI workflow error: {data['error']}")
    
    # Poll for completion
    start = time.time()
    while time.time() - start < TIMEOUT:
        history_resp = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=10)
        history = history_resp.json()
        
        if prompt_id in history:
            outputs = history[prompt_id].get("outputs", {})
            
            # Find the saved image output
            for node_id, output in outputs.items():
                # SaveImage returns {"images": [...]}
                images = output.get("images", [])
                if images:
                    img_info = images[0]
                    filename = img_info.get("filename", img_info if isinstance(img_info, str) else None)
                    subfolder = img_info.get("subfolder", "") if isinstance(img_info, dict) else ""
                    if filename:
                        # Download the generated image
                        img_data = requests.get(
                            f"{COMFY_URL}/view?filename={filename}&subfolder={subfolder}&type=output",
                            timeout=60,
                        )
                        img_data.raise_for_status()
                        return Image.open(io.BytesIO(img_data.content))

            
            # Completed but no images found
            raise RuntimeError(f"ComfyUI completed but no image outputs: {outputs}")
        
        time.sleep(2)
    
    raise RuntimeError(f"ComfyUI timed out after {TIMEOUT}s — no image received")


def check_comfyui_ready() -> bool:
    """Check if ComfyUI is reachable and has SD1.5 checkpoint loaded."""
    try:
        resp = requests.get(f"{COMFY_URL}/api/system_stats", timeout=5)
        data = resp.json()
        devices = data.get("system", {}).get("devices", [])
        for dev in devices:
            if dev.get("type") == "mps" and dev.get("vram_free", 0) > 1_000_000_000:
                return True
        return True  # Falls back if stats missing
    except Exception:
        return False


def get_comfy_lora_dir() -> Path:
    """Return the ComfyUI loras directory for trained LoRA placement."""
    return Path.home() / "Documents/comfy/ComfyUI/models/loras"


def place_lora(lora_path: str) -> str:
    """
    Symlink or copy a trained LoRA into ComfyUI's lora directory.
    Returns the filename to use in the workflow.
    """
    src = Path(lora_path)
    dest = get_comfy_lora_dir() / src.name
    
    if not dest.exists():
        import shutil
        shutil.copy2(src, dest)
    
    return src.name
