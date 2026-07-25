"""Tests for aeloria.publishing.fanvue."""
from unittest.mock import MagicMock, patch

import pytest

from aeloria.publishing.fanvue import FanvueClient, FanvuePost, PostType


class TestPostType:
    def test_all_post_types_exist(self):
        assert PostType.POST.value == "post"
        assert PostType.PPV_PHOTO.value == "ppv_photo"
        assert PostType.PPV_VIDEO.value == "ppv_video"
        assert PostType.SUBSCRIPTION.value == "subscription"


class TestFanvuePost:
    def test_fanvue_post_minimal(self):
        post = FanvuePost(post_type=PostType.POST, caption="Hello")
        assert post.post_type == PostType.POST
        assert post.caption == "Hello"
        assert post.media_bytes is None
        assert post.price is None

    def test_fanvue_post_ppv(self):
        post = FanvuePost(
            post_type=PostType.PPV_VIDEO,
            caption="Exclusive video",
            price=9.99,
            media_urls=["https://r2.example.com/vid.mp4"],
        )
        assert post.price == 9.99


class TestFanvueClient:
    def _mock_settings(self, api_key: str = ""):
        s = MagicMock()
        s.fanvue_api_key = api_key
        return s

    def test_noop_when_no_api_key_no_media(self):
        """No key + no media → ValueError about missing media (not API error)."""
        client = FanvueClient(self._mock_settings(""))
        post = FanvuePost(post_type=PostType.POST, caption="Test")
        with pytest.raises(ValueError, match="media_bytes or media_urls"):
            client.create_post(post)

    def test_create_post_noop_with_media_no_key(self):
        """No key but media present → _request raises RuntimeError, caught → returns {}."""
        client = FanvueClient(self._mock_settings(""))
        post = FanvuePost(
            post_type=PostType.POST,
            caption="Test",
            media_urls=["https://r2.example.com/img.jpg"],
        )
        result = client.create_post(post)
        assert result == {}

    def test_upload_media_no_key(self):
        """No key → upload_media returns empty string, no crash."""
        client = FanvueClient(self._mock_settings(""))
        result = client.upload_media(b"fake-bytes", "test.jpg", "image/jpeg")
        assert result == ""

    def test_post_type_round_trip(self):
        assert PostType("post") == PostType.POST
        assert PostType("ppv_photo") == PostType.PPV_PHOTO

    def test_create_post_success_mocked(self):
        """With key + media → mocked HTTP returns parsed response."""
        client = FanvueClient(self._mock_settings("valid-key"))

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "post_123", "status": "published"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value.post.return_value = mock_resp
        mock_client.__enter__.return_value.put.return_value = mock_resp

        with patch("aeloria.publishing.fanvue.httpx.Client", return_value=mock_client):
            post = FanvuePost(
                post_type=PostType.PPV_VIDEO,
                caption="Exclusive",
                price=5.99,
                media_urls=["https://r2.example.com/vid.mp4"],
            )
            result = client.create_post(post)

        assert result == {"id": "post_123", "status": "published"}
