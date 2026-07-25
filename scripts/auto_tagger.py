#!/usr/bin/env python3
"""Auto-tagger — generates detailed .txt captions for dataset training images.

Uses Moondream2 via FAL (cloud, $0.005/image) or local Qwen2.5-VL via Ollama.

For each image in a directory, generates a LoRA-training-ready caption with:
- Character trigger token
- Physical descriptors
- Pose, expression, wardrobe, lighting
- Saves as <image_name>.txt alongside the image

Usage:
    python scripts/auto_tagger.py --input /path/to/dataset --trigger "aeloria woman"
    python scripts/auto_tagger.py --input /path/to/images --trigger "aeloria woman" --backend moondream
    python scripts/auto_tagger.py --input /path/to/images --trigger "aeloria woman" --backend ollama
    python scripts/auto_tagger.py --input /path/to/images --dry-run  # just list files
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

TAGGER_PROMPT = """You are an expert image captioner for LoRA training data.
Describe this image for a training dataset caption. Include:
1. A trigger token at the start
2. Physical appearance: hair, eyes, skin, build
3. Pose and body position
4. Facial expression
5. Wardrobe (detailed: color, fabric, fit, accessories)
6. Setting/background
7. Lighting (direction, quality, time of day)
8. Camera (apparent focal length, angle, composition)

Write as a single flowing paragraph, 60-100 words.
Start with the trigger token. End with "photorealistic, detailed skin texture, natural lighting".

Trigger token: {trigger}

Caption:"""


def tag_with_moondream(image_path: str, trigger: str) -> str:
    """Use FAL Moondream2 to caption an image."""
    import fal_client

    os.environ.setdefault("FAL_KEY", os.environ.get("FAL_KEY", ""))
    url = fal_client.upload_file(str(image_path))
    prompt = TAGGER_PROMPT.format(trigger=trigger)

    result = fal_client.subscribe("fal-ai/moondream2", arguments={
        "image_url": url,
        "prompt": prompt,
    })
    caption = result.get("output", "").strip()

    # Ensure trigger token is at the start
    if not caption.lower().startswith(trigger.lower()):
        caption = f"{trigger}, {caption}"

    # Ensure training suffix
    if "photorealistic" not in caption.lower():
        caption += ", photorealistic, detailed skin texture, natural lighting"

    return caption


def tag_with_ollama(image_path: str, trigger: str, model: str = "qwen2.5vl:7b") -> str:
    """Use local Qwen2.5-VL via Ollama API to caption an image."""
    import base64

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    prompt = TAGGER_PROMPT.format(trigger=trigger)
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt, "images": [b64]}],
        "stream": False,
    })

    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/chat", "-d", payload],
            capture_output=True, text=True, timeout=180,
        )
        resp = json.loads(result.stdout)
        caption = resp.get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error("Ollama tagging failed for %s: %s", image_path, e)
        return ""

    if not caption.lower().startswith(trigger.lower()):
        caption = f"{trigger}, {caption}"
    if "photorealistic" not in caption.lower():
        caption += ", photorealistic, detailed skin texture, natural lighting"

    return caption


def process_directory(
    input_dir: str,
    trigger: str,
    backend: str = "moondream",
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict:
    """Process all images in a directory, generating .txt captions.

    Returns stats dict.
    """
    input_path = Path(input_dir)
    if not input_path.is_dir():
        logger.error("Input directory not found: %s", input_dir)
        return {"error": "directory not found"}

    image_exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    images = [f for f in input_path.iterdir() if f.suffix.lower() in image_exts]

    logger.info("Found %d images in %s", len(images), input_dir)

    stats = {"total": len(images), "tagged": 0, "skipped": 0, "failed": 0, "captions": []}

    for i, img_path in enumerate(images, 1):
        txt_path = img_path.with_suffix(".txt")

        if txt_path.exists() and not overwrite:
            logger.info("[%d/%d] Skip (exists): %s", i, len(images), img_path.name)
            stats["skipped"] += 1
            continue

        if dry_run:
            logger.info("[%d/%d] Dry run: %s → %s", i, len(images), img_path.name, txt_path.name)
            stats["skipped"] += 1
            continue

        logger.info("[%d/%d] Tagging: %s", i, len(images), img_path.name)
        t0 = time.time()

        try:
            if backend == "ollama":
                caption = tag_with_ollama(str(img_path), trigger)
            else:
                caption = tag_with_moondream(str(img_path), trigger)

            if caption:
                txt_path.write_text(caption)
                stats["tagged"] += 1
                stats["captions"].append({"image": img_path.name, "caption": caption[:100]})
                logger.info("  → %s (%.1fs)", txt_path.name, time.time() - t0)
            else:
                stats["failed"] += 1
                logger.warning("  → Empty caption")
        except Exception as e:
            stats["failed"] += 1
            logger.error("  → Failed: %s", e)

    logger.info("Done: %d tagged, %d skipped, %d failed", stats["tagged"], stats["skipped"], stats["failed"])
    return stats


def main():
    parser = argparse.ArgumentParser(description="Auto-tagger for LoRA training datasets")
    parser.add_argument("--input", "-i", required=True, help="Directory of training images")
    parser.add_argument("--trigger", "-t", default="aeloria woman", help="LoRA trigger token")
    parser.add_argument("--backend", "-b", choices=["moondream", "ollama"], default="moondream",
                        help="Vision model backend (default: moondream)")
    parser.add_argument("--dry-run", action="store_true", help="List files without tagging")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .txt files")
    args = parser.parse_args()

    stats = process_directory(args.input, args.trigger, args.backend, args.dry_run, args.overwrite)
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()