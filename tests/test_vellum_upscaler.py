"""Tests for aeloria.generation.vellum_upscaler."""
from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.vellum_upscaler import VellumUpscaler


class TestVellumUpscaler:
    def test_noop_when_api_key_missing(self, monkeypatch):
        """No Vellum key → returns image unchanged, no crash."""
        monkeypatch.setenv("VELLUM_API_KEY", "")
        from aeloria.config import get_settings
        vellum = VellumUpscaler(get_settings())
        result = vellum.upscale(b"fake-image-bytes")
        assert result == b"fake-image-bytes"

    def test_init_reads_vellum_key_from_settings(self, monkeypatch):
        monkeypatch.setenv("VELLUM_API_KEY", "vellum-test-key")
        from aeloria.config import get_settings
        get_settings.cache_clear()
        vellum = VellumUpscaler(get_settings())
        assert vellum._api_key == "vellum-test-key"

    def test_upscale_returns_bytes_mocked(self, monkeypatch):
        """When key is set, mocked HTTP returns upscaled bytes.

        The upscaler does a 2-call flow: POST the image → read `output_url`
        from the JSON response → GET that URL → return the downloaded bytes.
        """
        monkeypatch.setenv("VELLUM_API_KEY", "fake-key")
        from aeloria.config import get_settings
        get_settings.cache_clear()
        vellum = VellumUpscaler(get_settings())

        post_resp = MagicMock()
        post_resp.json.return_value = {"output_url": "https://cdn.example.com/up.png"}

        get_resp = MagicMock()
        get_resp.content = b"upscaled-image-bytes"

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = post_resp
        mock_client.__enter__.return_value.get.return_value = get_resp

        with patch("aeloria.generation.vellum_upscaler.httpx.Client", return_value=mock_client):
            result = vellum.upscale(b"original-image-bytes")

        assert result == b"upscaled-image-bytes"

    def test_upscale_graceful_on_http_error(self, monkeypatch):
        """HTTP error → returns original bytes."""
        monkeypatch.setenv("VELLUM_API_KEY", "fake-key")
        from aeloria.config import get_settings
        vellum = VellumUpscaler(get_settings())

        mock_client = MagicMock()
        error_resp = MagicMock()
        error_resp.raise_for_status.side_effect = Exception("network error")
        mock_client.__enter__.return_value.post.return_value = error_resp

        with patch("aeloria.generation.vellum_upscaler.httpx.Client", return_value=mock_client):
            result = vellum.upscale(b"original-bytes")

        assert result == b"original-bytes"
