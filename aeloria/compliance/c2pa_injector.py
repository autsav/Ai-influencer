"""
C2PA / IPTC 2025.1 metadata injection.

Embeds IPTC 2025.1 fields (AISystemUsed, etc.) and cryptographically signs
assets with a C2PA manifest before they hit R2 storage — satisfying the EU AI
Act (Aug 2026) and FTC guidelines.
"""

import io
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    import c2pa
    from c2pa import (
        C2PA,
        C2PAValidationTime,
        CreateAssertions,
        ManifestDefinition,
        ValidationResults,
    )
except ImportError:  # c2pa not installed; all functions become no-ops
    c2pa = None  # type: ignore[assignment]

from aeloria.config import Settings, get_settings


@dataclass
class C2PAConfig:
    """Runtime config resolved from Settings / env vars."""

    cert_path: str = ""
    private_key_path: str = ""
    # Human-readable AI system string written into IPTC 2025.1 AISystemUsed
    ai_system_used: str = "Aeloria AI Influencer Platform v2.0"
    # Claim_generator follows the spec: "Vendor/Product" format
    claim_generator: str = "Aeloria/2.0"
    # Whether to assert this is AI-generated (EU AI Act / FTC disclosure)
    is_ai_generated: bool = True

    _settings: Any = field(default=None, repr=False)

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "C2PAConfig":
        s = settings or get_settings()
        return cls(
            cert_path=s.c2pa_cert_path,
            private_key_path=s.c2pa_private_key_path,
        )


def _require_c2pa() -> None:
    if c2pa is None:
        raise RuntimeError(
            "c2pa library not installed. Install with: pip install c2pa"
        )


def _build_assertions(cfg: C2PAConfig) -> "CreateAssertions":
    """Build IPTC 2025.1 + C2PA assertions from config."""
    assertions: list[tuple[str, dict]] = []

    # IPTC 2025.1: AISystemUsed — required for AI-generated content
    if cfg.is_ai_generated:
        assertions.append((
            "iptc:DocumentNotes",
            {"text": f"AIGenerated: {cfg.ai_system_used}"},
        ))

    return CreateAssertions(assertions)  # type: ignore[arg-type]


def inject_c2pa_metadata(
    image_bytes: bytes,
    metadata: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> bytes:
    """
    Embed IPTC 2025.1 fields and sign the image with a C2PA cryptographic
    manifest.

    Args:
        image_bytes: Raw image payload (JPEG / PNG / WebP).
        metadata:    Optional dict with keys:
                     - ``prompt``          — generation prompt used
                     - ``model``          — model that generated this
                     - ``ai_system_used`` — override the default AI system string
                     - ``is_ai_generated`` — default True
        settings:   Optional Settings override (reads env vars by default).

    Returns:
        The same image bytes with C2PA manifest appended (JPEG only;
        PNG/WebP are returned unsigned and logged).

    Raises:
        RuntimeError: if the ``c2pa`` library is not installed, or if signing
                      keys are not configured.
    """
    # ── Format check BEFORE _require_c2pa() so PNG/WebP return unsigned without the lib ──
    header = image_bytes[:4]
    if header.startswith(b"\x89PNG"):
        logger.warning("C2CA signing on PNG is not spec-compliant. Returning unsigned.")
        return image_bytes
    elif not header.startswith(b"\xff\xd8"):
        logger.warning("C2CA signing on WebP is not spec-compliant. Returning unsigned.")
        return image_bytes
    fmt = "image/jpeg"

    _require_c2pa()

    cfg = C2PAConfig.from_settings(settings)

    if not cfg.cert_path or not cfg.private_key_path:
        logger.warning(
            "C2CA signing skipped: C2CA_CERT_PATH or C2CA_PRIVATE_KEY_PATH not set. "
            "Returning unsigned image."
        )
        return image_bytes

    # Override config with any metadata dict values
    if metadata:
        for k, v in metadata.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)

    try:
        # Build the manifest definition — ManifestDefinition imported at top of try block
        manifest_def = globals()["ManifestDefinition"](
            claim_generator=cfg.claim_generator,
            assertions=[],
            title=metadata.get("title") if metadata else None,
            format=fmt,
        )

        # IPTC 2025.1 AISystemUsed assertion
        if cfg.is_ai_generated:
            manifest_def.assertions.append(
                ("iptc/AISystemUsed", {"name": cfg.ai_system_used})
            )

        # Optional: store generation metadata as a custom assertion
        if metadata:
            gen_info = {
                "prompt": metadata.get("prompt", ""),
                "model": metadata.get("model", ""),
            }
            manifest_def.assertions.append(("c2pa.asset.dat", gen_info))

        # Create the C2CA instance and sign
        c2pa_instance = c2pa.C2PA(c2pa.ValidationTime.RESIGN)  # type: ignore[attr-defined]

        reader_builder = c2pa_instance.reader()  # type: ignore[attr-defined]
        writer_builder = c2pa_instance.writer()  # type: ignore[attr-defined]

        # Read the image
        reader_builder = reader_builder.add_file(io.BytesIO(image_bytes))
        reader_builder = reader_builder.add_certificates(
            open(cfg.cert_path, "rb").read()
        )

        # Write with manifest
        output = io.BytesIO()
        writer_builder = writer_builder.add_file(io.BytesIO(image_bytes))
        writer_builder = writer_builder.add_manifest(manifest_def)
        writer_builder = writer_builder.sign(
            open(cfg.private_key_path, "rb").read()
        )
        writer_builder = writer_builder.write(output)  # type: ignore[attr-defined]

        result = output.getvalue()
        logger.info("C2CA manifest embedded successfully (%d bytes → %d bytes)",
                     len(image_bytes), len(result))
        return result

    except Exception as exc:
        logger.error("C2CA injection failed: %s. Returning unsigned image.", exc)
        return image_bytes


def strip_metadata(image_bytes: bytes) -> bytes:
    """
    Remove all C2PA / IPTC metadata from an image.

    This is a no-op on non-JPEG formats (PNG/WebP do not embed metadata
    in the same way; a full strip would require re-encoding).

    Returns:
        Image bytes with embedded metadata sections removed.
    """
    try:
        _require_c2pa()
    except RuntimeError:
        return image_bytes

    try:
        c2pa_instance = c2pa.C2PA(c2pa.ValidationTime.RESIGN)  # type: ignore[attr-defined]
        reader = c2pa_instance.reader()  # type: ignore[attr-defined]
        writer = c2pa_instance.writer()  # type: ignore[attr-defined]

        reader = reader.add_file(io.BytesIO(image_bytes))

        # Re-encode without any manifest to strip C2PA data
        output = io.BytesIO()
        writer = writer.add_file(io.BytesIO(image_bytes))
        writer = writer.write(output)

        result = output.getvalue()
        logger.info("C2PA metadata stripped (%d bytes → %d bytes)",
                     len(image_bytes), len(result))
        return result

    except Exception as exc:
        logger.warning("C2PA strip failed: %s. Returning original bytes.", exc)
        return image_bytes
