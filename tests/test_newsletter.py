"""Tests for email newsletter generation."""
import pytest
from aeloria.distribution.newsletter import (
    generate_newsletter,
    select_top_posts,
    NewsletterPost,
    NewsletterResult,
)


def _make_post(pid, caption="Test caption", likes=10, reach=100, pillar="ai_tools"):
    return {
        "id": pid,
        "caption": caption,
        "image_url": f"https://example.com/{pid}.jpg",
        "likes": likes,
        "comments": 2,
        "shares": 1,
        "saves": 3,
        "reach": reach,
        "pillar": pillar,
    }


def _make_persona():
    from unittest.mock import MagicMock
    p = MagicMock()
    p.identity = {"name": "Aeloria"}
    p.voice = {"tone": "curious, confident"}
    return p


class TestSelectTopPosts:
    def test_selects_top_by_engagement(self):
        posts = [
            _make_post("p1", likes=5, reach=100),    # 0.11
            _make_post("p2", likes=30, reach=100),   # 0.36
            _make_post("p3", likes=10, reach=100),   # 0.16
        ]
        selected = select_top_posts(posts, max_posts=2)
        assert len(selected) == 2
        assert selected[0].post_id == "p2"  # highest engagement
        assert selected[1].post_id == "p3"

    def test_respects_max_posts(self):
        posts = [_make_post(f"p{i}", likes=i * 10) for i in range(10)]
        selected = select_top_posts(posts, max_posts=3)
        assert len(selected) == 3

    def test_empty_list(self):
        assert select_top_posts([]) == []

    def test_preserves_caption_and_image(self):
        posts = [_make_post("p1", caption="Great AI tool #AI")]
        selected = select_top_posts(posts)
        assert selected[0].caption == "Great AI tool #AI"
        assert selected[0].image_url == "https://example.com/p1.jpg"


class TestGenerateNewsletter:
    def test_generates_subject(self):
        posts = [_make_post("p1", caption="Amazing AI tool I found\n\n#AI")]
        result = generate_newsletter(posts, _make_persona())
        assert "Aeloria" in result.subject
        assert "Amazing AI tool I found" in result.subject

    def test_truncates_long_subject(self):
        posts = [_make_post("p1", caption="A" * 100)]
        result = generate_newsletter(posts, _make_persona())
        assert len(result.subject) <= 70  # "Aeloria — " + 60 chars + "..."

    def test_html_body_includes_images(self):
        posts = [_make_post("p1"), _make_post("p2")]
        result = generate_newsletter(posts, _make_persona())
        assert "<img" in result.html_body
        assert "p1.jpg" in result.html_body
        assert "p2.jpg" in result.html_body

    def test_text_body_strips_hashtags(self):
        posts = [_make_post("p1", caption="Great post\n\n#AI #Tech")]
        result = generate_newsletter(posts, _make_persona())
        assert "#AI" not in result.text_body
        assert "Great post" in result.text_body

    def test_html_strips_hashtags(self):
        posts = [_make_post("p1", caption="Great post\n\n#AI")]
        result = generate_newsletter(posts, _make_persona())
        assert "#AI" not in result.html_body

    def test_preheader_shows_count(self):
        posts = [_make_post("p1"), _make_post("p2")]
        result = generate_newsletter(posts, _make_persona())
        assert "2 posts" in result.preheader

    def test_empty_posts_returns_empty(self):
        result = generate_newsletter([], _make_persona())
        assert result.subject == ""
        assert result.post_count == 0

    def test_post_count(self):
        posts = [_make_post("p1"), _make_post("p2"), _make_post("p3")]
        result = generate_newsletter(posts, _make_persona(), max_posts=2)
        assert result.post_count == 2

    def test_has_generated_at(self):
        posts = [_make_post("p1")]
        result = generate_newsletter(posts, _make_persona())
        assert result.generated_at  # non-empty ISO timestamp

    def test_includes_pillar(self):
        posts = [_make_post("p1", pillar="founder_lifestyle")]
        result = generate_newsletter(posts, _make_persona())
        assert "founder_lifestyle" in result.html_body
        assert "founder_lifestyle" in result.text_body