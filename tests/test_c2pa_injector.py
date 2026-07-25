"""Tests for aeloria.compliance.c2pa_injector."""
import pytest

from aeloria.compliance.c2pa_injector import (
    _require_c2pa,
    inject_c2pa_metadata,
    strip_metadata,
)


class TestRequireC2PA:
    def test_raises_when_c2pa_absent(self):
        """Without the c2pa library installed the guard must fire."""
        with pytest.raises(RuntimeError, match="c2pa library not installed"):
            _require_c2pa()


class TestInjectC2PAMetadata:
    def test_noop_when_keys_missing(self, tmp_path, monkeypatch):
        """No cert/key configured → returns image verbatim."""
        monkeypatch.delenv("C2PA_CERT_PATH", raising=False)
        monkeypatch.delenv("C2PA_PRIVATE_KEY_PATH", raising=False)
        result = inject_c2pa_metadata(b"fake jpeg", {})
        assert result == b"fake jpeg"

    def test_png_returns_unsigned(self):
        """PNG is not C2PA-spec-compliant; falls back to unsigned copy."""
        # PNG magic bytes
        data = b"\x89PNG\r\n\x1a\n" + b"fake png data"
        result = inject_c2pa_metadata(data, {}, None)
        assert result == data

    def test_webp_returns_unsigned(self):
        """WebP is not C2PA-spec-compliant; falls back to unsigned copy."""
        data = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP"
        result = inject_c2pa_metadata(data, {}, None)
        assert result == data


class TestStripMetadata:
    def test_strip_jpeg_preserves_jpeg_markers(self):
        """Strip removes EXIF/IPTC but JPEG SOI/EOI markers stay intact."""
        # Minimal JPEG: SOI + APP0 (JFIF) + EOI
        jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\xff\xd9"
        result = strip_metadata(jpeg)
        assert result.startswith(b"\xff\xd8")
        assert result.endswith(b"\xff\xd9")
