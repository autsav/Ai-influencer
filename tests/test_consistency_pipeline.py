"""Tests for the two-pass consistency pipeline orchestrator."""
import pytest
from unittest.mock import MagicMock, patch

from aeloria.generation.consistency import ConsistencyResult, FaceCrop


class TestGenerateConsistent:
    @patch("aeloria.generation.consistency_pipeline.build_prompt")
    @patch("aeloria.generation.consistency_pipeline.detect_face_crop")
    @patch("aeloria.generation.consistency_pipeline.maybe_refine_face")
    @patch("aeloria.generation.consistency_pipeline.generate_image")
    def test_lora_fallback_when_no_reference(self, mock_gen, mock_refine, mock_detect, mock_prompt):
        """When no reference image is provided, falls back to LoRA-only generation."""
        from aeloria.generation.consistency_pipeline import generate_consistent

        mock_prompt.return_value = "test prompt"
        mock_gen.return_value = MagicMock(image_bytes=b"generated", cost_usd=0.05)
        mock_detect.return_value = None
        mock_refine.return_value = (b"generated", False)

        persona = MagicMock()
        settings = MagicMock()
        settings.pulid_enabled = True
        settings.face_ref_path = "/nonexistent/path.json"

        result = generate_consistent(
            brief={"prompt_seed": "office", "id": "test"},
            persona=persona,
            settings=settings,
            reference_bytes=None,
            use_pulid=True,
        )

        assert result.image_bytes == b"generated"
        assert result.cost_usd == 0.05
        assert result.detail_pass_applied is False
        assert result.identity_score == 0.0
        mock_gen.assert_called_once()

    @patch("aeloria.generation.pulid.httpx.get")
    @patch("fal_client.subscribe")
    @patch("aeloria.generation.consistency_pipeline.detect_face_crop")
    @patch("aeloria.generation.consistency_pipeline.maybe_refine_face")
    @patch("aeloria.generation.consistency_pipeline.generate_image")
    @patch("aeloria.generation.consistency_pipeline.build_prompt")
    def test_pulid_used_when_reference_provided(self, mock_prompt, mock_gen, mock_refine,
                                                 mock_detect, mock_subscribe, mock_httpx):
        """When reference image is provided, PuLID is used for Pass 1."""
        from aeloria.generation.consistency_pipeline import generate_consistent

        mock_prompt.return_value = "test prompt"
        mock_subscribe.return_value = {"images": [{"url": "https://example.com/img.png"}]}
        mock_resp = MagicMock()
        mock_resp.content = b"pulid-generated"
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.return_value = mock_resp
        mock_detect.return_value = FaceCrop(bbox=(100, 100, 400, 400), confidence=0.95,
                                            image_width=896, image_height=1152)
        mock_refine.return_value = (b"pulid-generated", False)

        persona = MagicMock()
        settings = MagicMock()
        settings.fal_key = "fake-key"
        settings.pulid_enabled = True
        settings.pulid_weight = 0.85
        settings.aeloria_lora_url = "https://example.com/lora.safetensors"
        settings.aeloria_lora_scale = 0.7
        settings.face_ref_path = "/nonexistent/path.json"

        result = generate_consistent(
            brief={"prompt_seed": "office", "id": "test"},
            persona=persona,
            settings=settings,
            reference_bytes=b"reference-image",
            use_pulid=True,
        )

        assert result.image_bytes == b"pulid-generated"
        mock_subscribe.assert_called_once()
        mock_gen.assert_not_called()

    @patch("fal_client.subscribe")
    @patch("aeloria.generation.consistency_pipeline.detect_face_crop")
    @patch("aeloria.generation.consistency_pipeline.maybe_refine_face")
    @patch("aeloria.generation.consistency_pipeline.generate_image")
    @patch("aeloria.generation.consistency_pipeline.build_prompt")
    def test_pulid_failure_falls_back_to_lora(self, mock_prompt, mock_gen, mock_refine,
                                               mock_detect, mock_subscribe):
        """When PuLID fails, falls back to LoRA-only generation."""
        from aeloria.generation.consistency_pipeline import generate_consistent

        mock_prompt.return_value = "test prompt"
        mock_subscribe.side_effect = Exception("PuLID down")
        mock_gen.return_value = MagicMock(image_bytes=b"lora-fallback", cost_usd=0.05)
        mock_detect.return_value = None
        mock_refine.return_value = (b"lora-fallback", False)

        persona = MagicMock()
        settings = MagicMock()
        settings.fal_key = "fake-key"
        settings.pulid_enabled = True
        settings.pulid_weight = 0.85
        settings.aeloria_lora_url = "https://example.com/lora.safetensors"
        settings.aeloria_lora_scale = 0.7
        settings.face_ref_path = "/nonexistent/path.json"

        result = generate_consistent(
            brief={"prompt_seed": "office", "id": "test"},
            persona=persona,
            settings=settings,
            reference_bytes=b"reference",
            use_pulid=True,
        )

        assert result.image_bytes == b"lora-fallback"
        assert result.cost_usd == 0.05
        mock_subscribe.assert_called_once()
        mock_gen.assert_called_once()

    @patch("aeloria.generation.consistency_pipeline.build_prompt")
    @patch("aeloria.generation.consistency_pipeline.detect_face_crop")
    @patch("aeloria.generation.consistency_pipeline.maybe_refine_face")
    @patch("aeloria.generation.consistency_pipeline.generate_image")
    def test_detail_pass_applied_for_small_face(self, mock_gen, mock_refine, mock_detect, mock_prompt):
        """Pass 2 is applied when face is small (< 256px)."""
        from aeloria.generation.consistency_pipeline import generate_consistent

        mock_prompt.return_value = "test prompt"
        mock_gen.return_value = MagicMock(image_bytes=b"base", cost_usd=0.05)
        mock_detect.return_value = FaceCrop(bbox=(100, 100, 200, 200), confidence=0.9,
                                            image_width=896, image_height=1152)
        mock_refine.return_value = (b"refined", True)

        persona = MagicMock()
        settings = MagicMock()
        settings.pulid_enabled = False
        settings.face_ref_path = "/nonexistent/path.json"
        settings.face_detailer_enabled = True

        result = generate_consistent(
            brief={"prompt_seed": "wide shot", "id": "test"},
            persona=persona,
            settings=settings,
            reference_bytes=None,
            use_pulid=False,
        )

        assert result.image_bytes == b"refined"
        assert result.detail_pass_applied is True