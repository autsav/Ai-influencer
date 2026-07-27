"""Tests for PuLID face identity generation module."""
import pytest
from unittest.mock import MagicMock, patch

from aeloria.generation.pulid import PULID_MODEL


class TestPulidModel:
    def test_model_is_flux_pulid(self):
        assert PULID_MODEL == "fal-ai/flux-pulid"


class TestPulidWeightClamping:
    @patch("aeloria.generation.pulid.httpx.get")
    @patch("fal_client.subscribe")
    def test_weight_gets_clamped_in_generate(self, mock_subscribe, mock_httpx):
        """Verify that pulid_weight is clamped before being sent to fal.ai."""
        settings = MagicMock()
        settings.fal_key = "fake-key"

        mock_subscribe.return_value = {"images": [{"url": "https://example.com/img.png"}]}
        mock_resp = MagicMock()
        mock_resp.content = b"fake-image-bytes"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.return_value = mock_resp

        from aeloria.generation.pulid import generate_with_pulid
        generate_with_pulid(
            prompt="test prompt",
            reference_image_bytes=b"fake-ref",
            settings=settings,
            pulid_weight=2.0,
        )

        call_args = mock_subscribe.call_args
        sent_weight = call_args.kwargs["arguments"]["pulid_weight"]
        assert sent_weight == 1.1


class TestPulidFallback:
    @patch("aeloria.generation.pulid.httpx.get")
    @patch("fal_client.subscribe")
    def test_lora_attached_when_url_provided(self, mock_subscribe, mock_httpx):
        settings = MagicMock()
        settings.fal_key = "fake-key"

        mock_subscribe.return_value = {"images": [{"url": "https://example.com/img.png"}]}
        mock_resp = MagicMock()
        mock_resp.content = b"fake-bytes"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.return_value = mock_resp

        from aeloria.generation.pulid import generate_with_pulid
        generate_with_pulid(
            prompt="test",
            reference_image_bytes=b"ref",
            settings=settings,
            lora_url="https://example.com/lora.safetensors",
            lora_scale=0.7,
        )

        args = mock_subscribe.call_args.kwargs["arguments"]
        assert "loras" in args
        assert args["loras"][0]["path"] == "https://example.com/lora.safetensors"
        assert args["loras"][0]["scale"] == 0.7

    @patch("aeloria.generation.pulid.httpx.get")
    @patch("fal_client.subscribe")
    def test_no_lora_when_url_none(self, mock_subscribe, mock_httpx):
        settings = MagicMock()
        settings.fal_key = "fake-key"

        mock_subscribe.return_value = {"images": [{"url": "https://example.com/img.png"}]}
        mock_resp = MagicMock()
        mock_resp.content = b"fake-bytes"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.return_value = mock_resp

        from aeloria.generation.pulid import generate_with_pulid
        generate_with_pulid(
            prompt="test",
            reference_image_bytes=b"ref",
            settings=settings,
            lora_url=None,
        )

        args = mock_subscribe.call_args.kwargs["arguments"]
        assert "loras" not in args