"""Tests for background removal and compositing."""
import pytest
from unittest.mock import MagicMock, patch
from aeloria.generation.compositing import (
    remove_background,
    composite_on_background,
    blur_background,
    CompositingError,
    REMOVE_BG_COST,
)


@patch("httpx.get")
@patch("fal_client.subscribe")
def test_remove_background_success(mock_subscribe, mock_httpx_get):
    mock_subscribe.return_value = {"image": {"url": "https://example.com/fg.png"}}
    mock_httpx_get.return_value = MagicMock(
        content=b"fake-png-bytes",
        raise_for_status=lambda: None,
    )
    settings = MagicMock()
    settings.fal_key = "fake-key"

    result = remove_background(b"source-image", settings)
    assert result == b"fake-png-bytes"


@patch("fal_client.subscribe")
def test_remove_background_failure_raises(mock_subscribe):
    mock_subscribe.side_effect = Exception("fal.ai error")
    settings = MagicMock()
    settings.fal_key = "fake-key"

    with pytest.raises(CompositingError, match="Background removal failed"):
        remove_background(b"source-image", settings)


@patch("fal_client.subscribe")
def test_remove_background_no_image_in_response(mock_subscribe):
    mock_subscribe.return_value = {"unexpected": "format"}
    settings = MagicMock()
    settings.fal_key = "fake-key"

    with pytest.raises(CompositingError, match="no image"):
        remove_background(b"source-image", settings)


def test_composite_on_background_with_local_file(tmp_path):
    """Test PIL compositing with a local background file."""
    from PIL import Image
    import io

    # Create a transparent foreground (10x10 red square)
    fg = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    fg_bytes = io.BytesIO()
    fg.save(fg_bytes, format="PNG")
    fg_bytes = fg_bytes.getvalue()

    # Create a background (50x50 blue)
    bg_path = tmp_path / "bg.png"
    bg = Image.new("RGBA", (50, 50), (0, 0, 255, 255))
    bg.save(str(bg_path))

    settings = MagicMock()
    result = composite_on_background(fg_bytes, str(bg_path), settings, position="center")
    assert len(result) > 0
    assert result[:2] == b"\xff\xd8"  # JPEG magic bytes


def test_composite_positions(tmp_path):
    """Test different position options don't crash."""
    from PIL import Image
    import io

    fg = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    fg_bytes = io.BytesIO()
    fg.save(fg_bytes, format="PNG")
    fg_bytes = fg_bytes.getvalue()

    bg_path = tmp_path / "bg.png"
    bg = Image.new("RGBA", (50, 50), (0, 0, 255, 255))
    bg.save(str(bg_path))

    settings = MagicMock()
    for pos in ["center", "left", "right", "bottom", "unknown"]:
        result = composite_on_background(fg_bytes, str(bg_path), settings, position=pos)
        assert len(result) > 0


def test_composite_with_scale(tmp_path):
    """Test foreground scaling."""
    from PIL import Image
    import io

    fg = Image.new("RGBA", (20, 20), (255, 0, 0, 255))
    fg_bytes = io.BytesIO()
    fg.save(fg_bytes, format="PNG")
    fg_bytes = fg_bytes.getvalue()

    bg_path = tmp_path / "bg.png"
    bg = Image.new("RGBA", (50, 50), (0, 0, 255, 255))
    bg.save(str(bg_path))

    settings = MagicMock()
    result = composite_on_background(fg_bytes, str(bg_path), settings, scale=0.5)
    assert len(result) > 0


def test_blur_background(tmp_path):
    """Test background blur produces valid JPEG."""
    from PIL import Image
    import io

    img = Image.new("RGB", (100, 100), (128, 128, 128))
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_bytes = img_bytes.getvalue()

    result = blur_background(img_bytes, blur_radius=5)
    assert len(result) > 0
    assert result[:2] == b"\xff\xd8"  # JPEG magic bytes