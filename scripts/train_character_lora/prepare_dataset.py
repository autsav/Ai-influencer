"""
Phase 1: Dataset Curation & Pre-processing
==========================================
1. Crop all reference_images to 1024x1024 (center crop)
2. Generate captions with BLIP-2 (Salesforce/blip-image-captioning-base)
3. Write metadata.jsonl  (28 train / 4 validation split)
4. Save cropped images to data/train/ and data/val/

Usage:
    python scripts/train_character_lora/prepare_dataset.py
"""

from __future__ import annotations

import json
import os
import random
import shutil
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration


# ── Config ────────────────────────────────────────────────────────────────────
REF_DIR   = PROJECT_ROOT / "reference_images"
OUT_DIR   = PROJECT_ROOT / "data"
TRAIN_DIR = OUT_DIR / "train"
VAL_DIR   = OUT_DIR / "val"
OUT_META  = OUT_DIR / "train_metadata.jsonl"

CROP_SIZE    = 1024
VAL_FRAC     = 4          # 1-in-N images go to validation
RANDOM_SEED  = 42
# ──────────────────────────────────────────────────────────────────────────────


def load_blip() -> tuple:
    """Load BLIP processor + model once."""
    print("Loading BLIP-2 captioning model...")
    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"  → device: {device}")
    processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
    model.to(device)
    model.eval()
    return processor, model, device


def caption_image(processor, model, device, image: Image.Image) -> str:
    """Generate a neutral caption for one PIL image."""
    inputs = processor(image, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=80)
    caption = processor.decode(out[0], skip_special_tokens=True)
    # Strip AI quality buzzwords from caption
    caption = _clean_caption(caption)
    return caption


def _clean_caption(caption: str) -> str:
    """Remove AI inflate词汇; keep only neutral visual description."""
    banned = {
        "high quality", "best quality", "masterpiece", "detailed",
        "beautiful", "gorgeous", "pretty", "stunning", "perfect",
        "professional", "photorealistic", "hyperrealistic", "ultrarealistic",
    }
    lower = caption.lower()
    for word in banned:
        lower = lower.replace(word, "")
    return lower.strip().rstrip(",").strip()


def crop_to_1024(img: Image.Image) -> Image.Image:
    """
    Center-crop to 1024x1024.  Images are 1344x768 (landscape).
    Crop to 1024x768 first (center), then resize to 1024x1024 (pad with black
    or stretch — we'll stretch to avoid losing face area).
    """
    w, h = img.size
    target = CROP_SIZE

    if w > h:
        # Landscape: crop width, keep full height
        left  = (w - target) // 2
        img   = img.crop((left, 0, left + target, h))
        # Resize to 1024x1024
        img   = img.resize((target, target), Image.LANCZOS)
    else:
        # Portrait or square
        top   = (h - target) // 2
        img   = img.crop((0, top, w, top + target))
        img   = img.resize((target, target), Image.LANCZOS)

    return img


def main():
    random.seed(RANDOM_SEED)
    os.makedirs(TRAIN_DIR, exist_ok=True)
    os.makedirs(VAL_DIR,  exist_ok=True)

    processor, model, device = load_blip()

    # Collect all reference images
    ref_files = sorted([f for f in REF_DIR.iterdir() if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])
    print(f"\nFound {len(ref_files)} reference images in {REF_DIR}")

    if len(ref_files) < 8:
        print("ERROR: need at least 8 reference images")
        sys.exit(1)

    # Shuffle with fixed seed, then split
    indices = list(range(len(ref_files)))
    random.shuffle(indices)

    # 1-in-VAL_FRAC for validation
    train_indices = [i for i in indices if i % VAL_FRAC != 0]
    val_indices   = [i for i in indices if i % VAL_FRAC == 0]

    # Guarantee at least 4 val images
    if len(val_indices) < 4 and len(train_indices) > 28:
        val_indices   = indices[-4:]
        train_indices = indices[:-4]

    print(f"Train: {len(train_indices)} | Validation: {len(val_indices)}")

    # ── Process ───────────────────────────────────────────────────────────────
    records: list[dict] = []

    for split, split_indices in [("train", train_indices), ("val", val_indices)]:
        out_split = TRAIN_DIR if split == "train" else VAL_DIR

        for idx in split_indices:
            src_path = ref_files[idx]
            img = Image.open(src_path).convert("RGB")
            cropped = crop_to_1024(img)

            # Save cropped image
            dst_path = out_split / src_path.name
            cropped.save(dst_path, "PNG")
            print(f"  [{split}] {src_path.name} → {dst_path.name}")

            # Caption
            caption = caption_image(processor, model, device, cropped)
            print(f"        caption: {caption[:80]}")

            records.append({
                "file_name":    dst_path.name,
                "caption":      caption,
                "original":     src_path.name,
                "split":        split,
            })

    # ── Write metadata ─────────────────────────────────────────────────────────
    with open(OUT_META, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    print(f"\n✓ Metadata written → {OUT_META}  ({len(records)} records)")
    print(f"  train images: {TRAIN_DIR}  ({len([r for r in records if r['split']=='train'])} images)")
    print(f"  val images:   {VAL_DIR}   ({len([r for r in records if r['split']=='val'])} images)")


if __name__ == "__main__":
    main()
