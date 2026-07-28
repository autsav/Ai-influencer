"""Tests for content repurposing engine."""
import pytest
from aeloria.distribution.repurpose import (
    reformat_aspect_ratio,
    adapt_caption_for_platform,
    repurpose_post,
    _strip_hashtags,
    _split_x_thread,
    RepurposeResult,
)


def test_reformat_aspect_ratio_returns_target():
    assert reformat_aspect_ratio("4:5", "9:16") == "9:16"
    assert reformat_aspect_ratio("1:1", "1.91:1") == "1.91:1"


def test_strip_hashtags_removes_hashtag_lines():
    caption = "Found this amazing AI tool\n\n#AI #Tech #Automation"
    clean = _strip_hashtags(caption)
    assert "#" not in clean
    assert "Found this amazing AI tool" in clean


def test_strip_hashtags_preserves_inline_text():
    caption = "This is great #amazing"
    clean = _strip_hashtags(caption)
    # Only removes lines that START with #
    assert "This is great #amazing" in clean


def test_adapt_caption_linkedin_strips_hashtags():
    ig_caption = "Found this amazing AI tool\n\n#AI #Tech #Automation"
    linkedin = adapt_caption_for_platform(ig_caption, "linkedin")
    assert isinstance(linkedin, str)
    assert "#" not in linkedin
    assert "Found this amazing AI tool" in linkedin


def test_adapt_caption_tiktok_truncates():
    long_caption = "A" * 200
    tiktok = adapt_caption_for_platform(long_caption, "tiktok")
    assert isinstance(tiktok, str)
    assert len(tiktok) == 150  # truncated to 150


def test_adapt_caption_x_thread_splits_long():
    long_caption = "A" * 350
    thread = adapt_caption_for_platform(long_caption, "x")
    assert isinstance(thread, list)
    assert len(thread) >= 2
    assert all(len(t) <= 280 for t in thread)


def test_adapt_caption_x_short_no_split():
    short = "Quick thought on AI tools."
    result = adapt_caption_for_platform(short, "x")
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0] == short


def test_adapt_caption_email_keeps_full_text():
    caption = "Long detailed post about AI automation\n\n#AI #Tech"
    email = adapt_caption_for_platform(caption, "email")
    assert "#" not in email  # hashtags stripped
    assert "Long detailed post" in email


def test_adapt_caption_instagram_unchanged():
    caption = "Test caption #AI #Tech"
    ig = adapt_caption_for_platform(caption, "instagram")
    assert ig == caption  # canonical — unchanged


def test_split_x_thread_short():
    result = _split_x_thread("Short tweet.", limit=280)
    assert result == ["Short tweet."]


def test_split_x_thread_long_multiple():
    text = ". ".join([f"Sentence number {i} about AI" for i in range(20)]) + "."
    result = _split_x_thread(text, limit=280)
    assert len(result) > 1
    assert all(len(t) <= 280 for t in result)
    # First tweet should contain "Sentence number 0"
    assert "Sentence number 0" in result[0]


def test_repurpose_post_returns_all_platforms():
    result = repurpose_post(
        image_url="https://example.com/img.png",
        video_url="https://example.com/vid.mp4",
        caption="Test caption #AI",
        pillar="ai_tools",
    )
    assert isinstance(result, RepurposeResult)
    assert "instagram" in result.platforms
    assert "tiktok" in result.platforms
    assert "linkedin" in result.platforms
    assert "x" in result.platforms
    assert "email" in result.platforms


def test_repurpose_post_tiktok_gets_video():
    result = repurpose_post(
        image_url="https://example.com/img.png",
        video_url="https://example.com/vid.mp4",
        caption="Test #AI",
        pillar="ai_tools",
    )
    assert result.platforms["tiktok"]["media_url"] == "https://example.com/vid.mp4"
    assert result.platforms["tiktok"]["aspect"] == "9:16"


def test_repurpose_post_linkedin_gets_image():
    result = repurpose_post(
        image_url="https://example.com/img.png",
        video_url=None,
        caption="Test #AI",
        pillar="founder_lifestyle",
    )
    assert result.platforms["linkedin"]["media_url"] == "https://example.com/img.png"
    assert result.platforms["linkedin"]["aspect"] == "1.91:1"


def test_repurpose_post_email_no_media():
    result = repurpose_post(
        image_url="https://example.com/img.png",
        caption="Test #AI",
        pillar="ai_tools",
    )
    assert result.platforms["email"]["media_url"] is None
    assert result.platforms["email"]["aspect"] is None


def test_repurpose_post_x_caption_is_thread():
    long_caption = "A" * 350
    result = repurpose_post(caption=long_caption, pillar="ai_tools")
    assert isinstance(result.platforms["x"]["caption"], list)


def test_repurpose_post_pillar_recorded():
    result = repurpose_post(caption="Test", pillar="case_studies")
    assert result.platforms["instagram"]["pillar"] == "case_studies"