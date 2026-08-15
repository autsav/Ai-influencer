"""Tests for aeloria.generation.video_engine."""
from unittest.mock import MagicMock, patch

import pytest

from aeloria.generation.video_engine import VideoEngineConfig, generate_video


class TestVideoEngineConfig:
    def test_default_engine_is_kling(self):
        cfg = VideoEngineConfig()
        assert cfg.engine == "kling"

    def test_from_settings(self, monkeypatch):
        # Kling is hosted on fal.ai — VideoEngineConfig.from_settings reads FAL_KEY
        # for the kling_api_key slot (see video_engine.py:38, fixed 2026-07-29).
        monkeypatch.setenv("FAL_KEY", "kling-key")
        monkeypatch.setenv("WAN_API_KEY", "wan-key")
        from aeloria.config import get_settings
        get_settings.cache_clear()
        cfg = VideoEngineConfig.from_settings()
        assert cfg.kling_api_key == "kling-key"
        assert cfg.wan_api_key == "wan-key"


class TestGenerateVideo:
    def test_unknown_engine_raises(self, monkeypatch):
        """Unknown engine raises ValueError even when get_settings() returns a valid engine."""
        monkeypatch.setenv("KLING_API_KEY", "some-key")
        from aeloria.config import get_settings
        get_settings.cache_clear()

        with patch("aeloria.generation.video_engine.get_settings", return_value=get_settings()):
            with pytest.raises(ValueError, match="Unknown video engine"):
                generate_video(b"fake", "prompt", "unknown")

    def test_noop_when_image_bytes_empty(self, monkeypatch):
        """Empty image bytes: Kling upload returns no URL → RuntimeError."""
        mock_settings = MagicMock()
        mock_settings.kling_api_key = "fake-key"
        mock_settings.wan_api_key = "fake-key"
        mock_settings.kling_model = "kling-video/v2.5-turbo/pro/image-to-video"

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"url": ""}

        with patch("aeloria.generation.video_engine.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp
            with pytest.raises(RuntimeError, match="no video URL"):
                generate_video(b"", "slow orbit", "kling", mock_settings)

    def test_kling_raises_without_api_key(self):
        """Kling with empty API key raises RuntimeError."""
        mock_settings = MagicMock()
        mock_settings.kling_api_key = ""
        mock_settings.wan_api_key = ""
        mock_settings.kling_model = "kling-video/v2.5-turbo/pro/image-to-video"

        with pytest.raises(RuntimeError, match="KLING_API_KEY"):
            generate_video(b"fake-image-bytes", "camera orbit", "kling", mock_settings)

    def test_wan_raises_without_api_key(self):
        """Wan with empty API key raises RuntimeError."""
        mock_settings = MagicMock()
        mock_settings.kling_api_key = ""
        mock_settings.wan_api_key = ""
        mock_settings.kling_model = "kling-video/v2.5-turbo/pro/image-to-video"

        with pytest.raises(RuntimeError, match="WAN_API_KEY"):
            generate_video(b"fake-image-bytes", "slow pan", "wan", mock_settings)

    def test_kling_success(self):
        """Kling with valid key + mocked HTTP returns video bytes."""
        mock_settings = MagicMock()
        mock_settings.kling_api_key = "valid-key"
        mock_settings.wan_api_key = ""
        mock_settings.kling_model = "kling-video/v2.5-turbo/pro/image-to-video"

        upload_resp = MagicMock()
        upload_resp.json.return_value = {"url": "https://fal.storage/image.jpg"}

        video_resp = MagicMock()
        video_resp.content = b"fake-video-bytes"

        mock_post = MagicMock(side_effect=[upload_resp, video_resp])
        mock_client = MagicMock()
        mock_client.__enter__.return_value.post = mock_post
        mock_client.__enter__.return_value.get.return_value = video_resp

        with patch("aeloria.generation.video_engine.httpx.Client", return_value=mock_client):
            result = generate_video(b"fake-image", "slow orbit", "kling", mock_settings)

        assert result == b"fake-video-bytes"
