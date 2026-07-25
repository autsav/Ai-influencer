"""
Vellum AI skin micro-texture upscaler.

Processes raw fal.ai output through Vellum to rebuild natural skin pores,
micro-tonal variations, and biological textures — fixing the "plastic" AI look.
"""

import io
import logging

import httpx

from aeloria.config import Settings, get_settings

logger = logging.getLogger(__name__)


class VellumUpscaler:
    """
    Calls the Vellum AI upscale endpoint to add biological skin micro-textures.

    Usage:
        vellum = VellumUpscaler()
        refined_bytes = vellum.upscale(raw_image_bytes, prompt=original_prompt)
    """

    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._api_key = s.vellum_api_key
        self._endpoint = "https://api.vellum.ai/v1/upscale/skin"  # placeholder; adjust to actual Vellum API
        self._timeout = 60.0

    def upscale(
        self,
        image_bytes: bytes,
        prompt: str | None = None,
        resemblance: float = 0.8,
        creativity: float = 0.3,
    ) -> bytes:
        """
        Send image through Vellum's skin micro-texture pipeline.

        Args:
            image_bytes: Raw image from fal.ai generation.
            prompt:      Original generation prompt (used as context for
                         Vellum's refinement to stay on-model).
            resemblance: How much to preserve identity (0.0–1.0).
            creativity:  How much texture variety to add (0.0–1.0).

        Returns:
            Refined image bytes (JPEG/PNG).

        Raises:
            RuntimeError: if Vellum API key is not configured or call fails.
        """
        if not self._api_key:
            logger.warning("Vellum API key not configured — skipping upscale, returning original.")
            return image_bytes

        files = {"image": ("image.jpg", image_bytes, "image/jpeg")}
        data = {
            "resemblance": str(resemblance),
            "creativity": str(creativity),
        }
        if prompt:
            data["prompt"] = prompt

        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    self._endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    data=data,
                    files=files,
                )
                resp.raise_for_status()
                result = resp.json()

            output_url = result.get("output_url") or result.get("image_url")
            if not output_url:
                raise RuntimeError(f"Vellum returned no output URL: {result}")

            # Download the upscaled image
            with httpx.Client(timeout=self._timeout) as client:
                img_resp = client.get(output_url)
                img_resp.raise_for_status()

            logger.info(
                "Vellum upscale done: %d bytes → %d bytes",
                len(image_bytes),
                len(img_resp.content),
            )
            return img_resp.content

        except httpx.HTTPStatusError as exc:
            logger.error("Vellum HTTP error %s: %s", exc.response.status_code, exc.response.text)
            return image_bytes
        except Exception as exc:
            logger.error("Vellum upscale failed: %s. Returning original.", exc)
            return image_bytes
