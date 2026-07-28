"""Background removal and compositing for Aeloria images.

Uses fal.ai's remove-background endpoint to isolate Aeloria from the
generated background, then composites onto custom backgrounds (branded
environments, product shots, event backdrops) without full regeneration.

Usage:
    from aeloria.generation.compositing import remove_background, composite_on_background
    # Isolate Aeloria
    foreground = remove_background(image_bytes, settings)
    # Place on branded background
    composited = composite_on_background(foreground, "https://r2.dev/branded_bg.jpg", settings)
"""
import logging
import io
import httpx

log = logging.getLogger(__name__)

REMOVE_BG_MODEL = "fal-ai/auraflow/remove-background"
REMOVE_BG_COST = 0.02

COMPOSITE_MODEL = "fal-ai/flux/dev/inpainting"
COMPOSITE_COST = 0.04


class CompositingError(Exception):
    pass


def remove_background(image_bytes: bytes, settings) -> bytes:
    """Remove the background from an image, returning a PNG with transparency.

    Uses fal.ai's remove-background endpoint. The result is a PNG with
    a transparent background where Aeloria is isolated.

    Args:
        image_bytes: Source image bytes (JPEG/PNG)
        settings: App settings (needs fal_key)

    Returns:
        PNG bytes with transparent background

    Raises:
        CompositingError: If the API call fails
    """
    import os
    import base64
    import fal_client

    os.environ["FAL_KEY"] = settings.fal_key

    # Encode image as data URI
    data_uri = "data:image/png;base64," + base64.b64encode(image_bytes).decode()

    log.info("Removing background via fal.ai")

    try:
        result = fal_client.subscribe(REMOVE_BG_MODEL, arguments={"image": data_uri})
        image_url = result.get("image", {}).get("url")
        if not image_url:
            image_url = result.get("output", {}).get("image_url")
        if not image_url:
            raise CompositingError(f"Remove-bg returned no image: {result}")

        resp = httpx.get(image_url, timeout=60)
        resp.raise_for_status()

        log.info("Background removed: %d bytes, cost=$%.4f", len(resp.content), REMOVE_BG_COST)
        return resp.content

    except Exception as e:
        log.error("Background removal failed: %s", e)
        raise CompositingError(f"Background removal failed: {e}") from e


def composite_on_background(
    foreground_bytes: bytes,
    background_url: str,
    settings,
    position: str = "center",
    scale: float = 1.0,
) -> bytes:
    """Composite a foreground (transparent PNG) onto a background image.

    Uses PIL for simple compositing — no fal.ai cost for the blend itself.
    The foreground is placed on the background at the specified position.

    Args:
        foreground_bytes: PNG bytes with transparency (from remove_background)
        background_url: URL to the background image, or local path
        settings: App settings
        position: "center", "left", "right", "bottom"
        scale: Scale factor for the foreground (1.0 = original size)

    Returns:
        Composited JPEG bytes
    """
    from PIL import Image

    # Load foreground
    fg = Image.open(io.BytesIO(foreground_bytes)).convert("RGBA")

    # Load background
    if background_url.startswith("http"):
        resp = httpx.get(background_url, timeout=60)
        resp.raise_for_status()
        bg = Image.open(io.BytesIO(resp.content)).convert("RGBA")
    else:
        bg = Image.open(background_url).convert("RGBA")

    # Scale foreground
    if scale != 1.0:
        new_size = (int(fg.width * scale), int(fg.height * scale))
        fg = fg.resize(new_size, Image.LANCZOS)

    # Calculate position
    bg_w, bg_h = bg.size
    fg_w, fg_h = fg.size

    if position == "center":
        x = (bg_w - fg_w) // 2
        y = (bg_h - fg_h) // 2
    elif position == "left":
        x = 0
        y = (bg_h - fg_h) // 2
    elif position == "right":
        x = bg_w - fg_w
        y = (bg_h - fg_h) // 2
    elif position == "bottom":
        x = (bg_w - fg_w) // 2
        y = bg_h - fg_h
    else:
        x = (bg_w - fg_w) // 2
        y = (bg_h - fg_h) // 2

    # Composite
    bg.paste(fg, (x, y), fg)  # third arg = alpha mask
    result = bg.convert("RGB")

    # Save as JPEG
    output = io.BytesIO()
    result.save(output, format="JPEG", quality=95)
    composited = output.getvalue()

    log.info("Composited: fg=%dx%d → bg=%dx%d at %s", fg_w, fg_h, bg_w, bg_h, position)
    return composited


def blur_background(image_bytes: bytes, blur_radius: int = 15) -> bytes:
    """Blur the background of an image while keeping the subject sharp.

    This is a simple PIL-based effect — detects the center region as "subject"
    and blurs the edges. For production, use SAM for proper subject detection.

    Args:
        image_bytes: Source image bytes
        blur_radius: Gaussian blur radius in pixels

    Returns:
        JPEG bytes with blurred background
    """
    from PIL import Image, ImageFilter

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size

    # Create a blurred version
    blurred = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    # Create a mask: sharp in center, blurred at edges
    mask = Image.new("L", (w, h), 0)
    # Center ellipse region
    cx, cy = w // 2, h // 2
    rx, ry = int(w * 0.35), int(h * 0.45)
    for x in range(w):
        for y in range(h):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                mask.putpixel((x, y), 255)

    # Composite: sharp where mask=255, blurred where mask=0
    result = Image.composite(img, blurred, mask)

    output = io.BytesIO()
    result.save(output, format="JPEG", quality=95)
    return output.getvalue()