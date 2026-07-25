"""Professional photography post-processing pipeline.

All transforms are local (PIL / numpy) — zero FAL cost.

Applied in order after a raw AI image is returned:
  1. Auto white-balance + exposure micro-adjust
  2. Selective unsharp mask (sharpen subject, leave background soft)
  3. Film grain overlay (if film stock was in the generation prompt)
  4. Subtle vignette (portrait-calibrated: lighter than landscape)

Call signature:
    processed_bytes = process_and_save(image_bytes: bytes, prompt: str | None = None) -> bytes
    processed_path  = process_and_save(image_path: str,  prompt: str | None = None) -> str

The prompt is inspected to detect film-stock keywords (kodak portra,
cinestill, fuji, gold 200…) — when found, grain is applied.  Pass None
to skip grain entirely.
"""

from __future__ import annotations

import io
import math
import os
import tempfile
from pathlib import Path
from typing import Literal

from PIL import Image as _PILImage
from PIL import Image, ImageFilter, ImageEnhance

# ── internal helpers ──────────────────────────────────────────────────────────

def _load_pil(source: bytes | str | "Image.Image") -> "Image.Image":
    from PIL import Image
    if isinstance(source, Image.Image):
        return source
    if isinstance(source, bytes):
        return Image.open(io.BytesIO(source))
    return Image.open(source)


def _save_pil(img: "Image.Image", fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=95)
    buf.seek(0)
    return buf.read()


# ── Film grain tile (32×32 px, procedurally generated once per process) ───────
#
# Real film grain is spatially correlated (clustered silver halide crystals)
# and chromatically neutral.  We approximate this with:
#   1. A monochrome base noise field at moderate amplitude
#   2. A very-low-amplitude chromatic layer to capture halation / colour noise
#
# We generate a 32×32 tile and Tile/repeat it across the image — any tiled
# artefact is too fine to see at normal viewing sizes.

_GRAIN_TILE: "Image.Image | None" = None
_GRAIN_TILE_SIZE = 32


def _get_grain_tile() -> "Image.Image":
    global _GRAIN_TILE
    if _GRAIN_TILE is None:
        import numpy as np
        rng = np.random.default_rng(12345)           # deterministic seed
        base = rng.normal(0, 22, (_GRAIN_TILE_SIZE, _GRAIN_TILE_SIZE))
        # barely-perceptible warm colour noise
        chrom_r = rng.normal(0, 3, (_GRAIN_TILE_SIZE, _GRAIN_TILE_SIZE))
        chrom_b = rng.normal(0, 3, (_GRAIN_TILE_SIZE, _GRAIN_TILE_SIZE))
        grain = (base[..., None] + np.stack([chrom_r, np.zeros_like(base), chrom_b], axis=-1))
        grain = grain.astype("int16") + 128           # shift to 0-255 range
        grain = grain.clip(0, 255).astype("uint8")

        from PIL import Image
        _GRAIN_TILE = Image.fromarray(grain, mode="RGB")

    return _GRAIN_TILE


# ── Individual transform stages ───────────────────────────────────────────────

def auto_wb_exposure(img: "Image.Image", strength: float = 0.4) -> "Image.Image":
    """Slight automatic white-balance + exposure micro-adjust via PIL ImageStat.

    `strength` controls how aggressively we shift the means toward neutral:
      0.0 = no change
      1.0 = full pull to neutral (usually too harsh)
    0.35–0.45 is a good working range for portrait work.
    """
    import numpy as np
    from PIL import Image, ImageStat, ImageEnhance

    # Convert to numpy once
    arr = np.array(img.convert("RGB")).astype("float32")

    # Per-channel mean
    r_mean, g_mean, b_mean = arr[:, :, 0].mean(), arr[:, :, 1].mean(), arr[:, :, 2].mean()
    overall = (r_mean + g_mean + b_mean) / 3.0

    # Exposure pull: if overall is too dark / too bright, scale gently
    exposure_scale = (overall / 128.0) ** (strength * 0.3)
    exposure_scale = float(exposure_scale)
    arr *= max(0.7, min(1.35, exposure_scale))

    # White-balance: pull the most extreme channel toward the other two
    # (if image is warm / orange, r_mean > g_mean,b_mean → reduce r)
    channel_means = [r_mean, g_mean, b_mean]
    for c in range(3):
        delta = channel_means[c] - (channel_means[(c + 1) % 3] + channel_means[(c + 2) % 3]) / 2.0
        if abs(delta) > 5:          # only act if there's real colour cast
            shift = delta * strength * 0.08
            arr[:, :, c] = (arr[:, :, c] - shift).clip(0, 255)

    # Gentle contrast boost (PILEnhance — cheap and reliable)
    result = Image.fromarray(arr.astype("uint8"), mode="RGB")
    enhancer = ImageEnhance.Contrast(result)
    result = enhancer.enhance(1.0 + 0.05 * strength)
    return result


def selective_sharpen(
    img: "Image.Image",
    amount: float = 1.4,
    radius: float = 0.8,
    threshold: int = 3,
) -> "Image.Image":
    """Apply unsharp mask only on mid-high-frequency detail (portrait skin /
    hair / clothing) without amplifying background noise further.

    PIL's ImageFilter.UnsharpMask does:
      sharpened = original + (original - blurred) * amount
    We pre-blur the input so the mask is already spatially limited.
    """
    from PIL import ImageFilter

    # Unsharp mask: apply directly to img via the filter() instance method
    unsharp = ImageFilter.UnsharpMask(
        radius=radius,
        percent=int(amount * 100),
        threshold=threshold,
    )
    sharpened = img.filter(unsharp)

    # Blend: original 60% + sharpened 40% — keeps it natural
    import numpy as np
    arr_orig = np.array(img.convert("RGB")).astype("float32")
    arr_sharp = np.array(sharpened.convert("RGB")).astype("float32")
    arr_blend = arr_orig * 0.60 + arr_sharp * 0.40
    return Image.fromarray(arr_blend.clip(0, 255).astype("uint8"), mode="RGB")


def film_grain(
    img: "Image.Image",
    intensity: float = 0.18,
) -> "Image.Image":
    """Overlay procedurally-generated film grain on the image.

    `intensity` 0.0–0.3 is a good working range; 0.18–0.22 mimics
    Kodak Portra 800 pushed, 0.10–0.14 mimics fresh Portra 400.
    """
    from PIL import Image

    tile = _get_grain_tile()
    w, h = img.size

    # Tile the 32×32 grain tile to cover the full image
    tile_w, tile_h = tile.size
    bg = Image.new("RGB", (w, h))
    for y in range(0, h + tile_h, tile_h):
        for x in range(0, w + tile_w, tile_w):
            bg.paste(tile, (x % w, y % h))

    # Blend: original + grain * intensity
    import numpy as np
    arr_img  = np.array(img.convert("RGB")).astype("float32")
    arr_grain = np.array(bg.convert("RGB")).astype("float32") - 128.0   # centre on 0
    blended = arr_img + arr_grain * intensity
    return Image.fromarray(blended.clip(0, 255).astype("uint8"), mode="RGB")


def vignette(
    img: "Image.Image",
    strength: float = 0.22,
    radius: float = 0.75,
) -> "Image.Image":
    """Subtle radial darkening — portrait-calibrated (lighter than landscape).

    `strength`: 0.0 = no change, 1.0 = very dark corners.
    Portrait work suits 0.15–0.25; fashion / beauty up to 0.30.
    """
    import numpy as np

    w, h = img.size
    cx, cy = w / 2, h / 2
    # Elliptical mask so vertical edges darken faster than horizontal
    Y, X = np.ogrid[:h, :w]
    dist_x = ((X - cx) / (w * radius)) ** 2
    dist_y = ((Y - cy) / (h * radius * 1.4)) ** 2      # flatter vertically
    dist = np.sqrt(dist_x + dist_y).clip(0, 1)          # 0 = centre, 1 = corners
    vignette_map = (1.0 - dist * strength).clip(0, 1)

    arr = np.array(img.convert("RGB")).astype("float32")
    arr *= vignette_map[..., np.newaxis]                # (H,W) → (H,W,1), broadcast to HWC
    return Image.fromarray(arr.clip(0, 255).astype("uint8"), mode="RGB")


# ── Detect film stock from prompt ────────────────────────────────────────────

def detect_film_intensity(prompt: str | None) -> float:
    """Inspect the generation prompt for film-stock keywords.
    Returns a grain intensity in the 0.10–0.22 range, or 0.0 if no
    recognised film stock is found (i.e. digital pipeline, skip grain).

    Keyword → approximate grain level:
      Kodak Gold 200        → 0.10  (consumer-grade, fine grain)
      Kodak Portra 400      → 0.14  (professional colour, moderate)
      Fujifilm Pro 400H     → 0.13  (very fine grain, velvet)
      Kodak Portra 800      → 0.20  (fast, visible grain, pushed)
      Cinestill 800T         → 0.22  (tungsten, halation, distinctive)
      Generic "film"         → 0.15  (catch-all fallback)
    """
    if not prompt:
        return 0.0
    prompt_lower = prompt.lower()
    if "cinestill" in prompt_lower:
        return 0.22
    if "portra 800" in prompt_lower or "portra800" in prompt_lower:
        return 0.20
    if "portra 400" in prompt_lower or "portra400" in prompt_lower:
        return 0.14
    if "portra" in prompt_lower:
        return 0.15
    if "gold 200" in prompt_lower or "gold200" in prompt_lower:
        return 0.10
    if "fuji" in prompt_lower or "pro 400h" in prompt_lower:
        return 0.13
    if "film grain" in prompt_lower or "film stock" in prompt_lower:
        return 0.15
    return 0.0


# ── Main entry point ──────────────────────────────────────────────────────────

def process_and_save(
    source: bytes | str,
    prompt: str | None = None,
    output_dir: str | None = None,
    output_fmt: str = "JPEG",
) -> bytes | str:
    """Run the full post-processing pipeline on an image.

    Args
        source   : raw image bytes or path to an image file on disk
        prompt   : generation prompt (used to detect film-stock for grain)
        output_dir: directory to write the processed file.
                   None  → return bytes (in-memory).
                   str   → write to output_dir/ and return the path.
        output_fmt: image format for the output file ("JPEG" or "PNG")

    Returns
        bytes  if output_dir is None  (caller is responsible for saving)
        str    (path to the written file) if output_dir is set
    """
    img = _load_pil(source)

    # Stage 1: micro colour / exposure correction
    img = auto_wb_exposure(img, strength=0.40)

    # Stage 2: selective sharpen (skin / hair / clothing detail)
    img = selective_sharpen(img, amount=1.4, radius=0.8, threshold=3)

    # Stage 3: film grain (only if prompt contains recognised film-stock keyword)
    grain_intensity = detect_film_intensity(prompt)
    if grain_intensity > 0:
        img = film_grain(img, intensity=grain_intensity)

    # Stage 4: subtle portrait vignette
    img = vignette(img, strength=0.22, radius=0.75)

    # Save
    if output_dir is None:
        return _save_pil(img, fmt=output_fmt)

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix=f".{output_fmt.lower()}", dir=output_dir)
    os.close(fd)
    img.save(tmp, format=output_fmt, quality=95)
    return tmp
