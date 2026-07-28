"""Email newsletter generation and capture system.

Auto-generates a weekly newsletter from the week's best-performing posts.
Provides a capture mechanism (IG bio link → landing page → email list).

Usage:
    from aeloria.distribution.newsletter import generate_newsletter, NewsletterResult
    result = generate_newsletter(weekly_posts, persona, settings)
    print(result.subject)
    print(result.html_body)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass
class NewsletterPost:
    """A post selected for the newsletter."""
    post_id: str
    caption: str
    image_url: str | None = None
    engagement_rate: float = 0.0
    pillar: str = ""


@dataclass
class NewsletterResult:
    """Generated newsletter content."""
    subject: str = ""
    preheader: str = ""
    html_body: str = ""
    text_body: str = ""
    post_count: int = 0
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()


def select_top_posts(posts: list[dict], max_posts: int = 5) -> list[NewsletterPost]:
    """Select the top-performing posts for the newsletter.

    Sorts by engagement rate and returns the top N.
    """
    def engagement_rate(p):
        reach = p.get("reach", 0)
        if reach == 0:
            return 0.0
        return (p.get("likes", 0) + p.get("comments", 0) +
                p.get("shares", 0) + p.get("saves", 0)) / reach

    sorted_posts = sorted(posts, key=engagement_rate, reverse=True)
    selected = sorted_posts[:max_posts]

    return [
        NewsletterPost(
            post_id=str(p.get("id", "")),
            caption=p.get("caption", ""),
            image_url=p.get("image_url"),
            engagement_rate=engagement_rate(p),
            pillar=p.get("pillar", ""),
        )
        for p in selected
    ]


def _strip_hashtags(caption: str) -> str:
    """Remove hashtag lines from caption for newsletter."""
    lines = caption.split("\n")
    clean = [l for l in lines if not l.strip().startswith("#")]
    return "\n".join(clean).strip()


def generate_newsletter(
    weekly_posts: list[dict],
    persona,
    settings=None,
    max_posts: int = 5,
) -> NewsletterResult:
    """Generate a weekly newsletter from the best posts.

    Args:
        weekly_posts: List of post dicts with metrics (id, caption, image_url, reach, likes, etc.)
        persona: Loaded persona (for voice/tone)
        settings: App settings
        max_posts: Maximum posts to include

    Returns:
        NewsletterResult with subject, preheader, HTML and text bodies
    """
    top_posts = select_top_posts(weekly_posts, max_posts)
    if not top_posts:
        return NewsletterResult(subject="", post_count=0)

    persona_name = persona.identity.get("name", "Aeloria") if hasattr(persona, "identity") else "Aeloria"
    persona_tone = persona.voice.get("tone", "") if hasattr(persona, "voice") else ""

    # Subject line: use the top post's hook
    top_caption = top_posts[0].caption if top_posts else ""
    first_line = top_caption.split("\n")[0] if top_caption else "This week's updates"
    prefix = f"{persona_name} — "
    max_caption_len = 60 - len(prefix)
    if len(first_line) > max_caption_len:
        subject = f"{prefix}{first_line[:max_caption_len]}..."
    else:
        subject = f"{prefix}{first_line}"

    # Preheader
    preheader = f"{len(top_posts)} posts this week · Top engagement: {top_posts[0].engagement_rate:.1%}"

    # Build HTML body
    html_parts = [
        f"<html><body style='font-family: sans-serif; max-width: 600px; margin: 0 auto;'>",
        f"<h2 style='color: #333;'>{persona_name}'s Weekly Digest</h2>",
        f"<p style='color: #666; font-size: 14px;'>{preheader}</p>",
        f"<hr style='border: none; border-top: 1px solid #eee; margin: 20px 0;'>",
    ]

    for i, post in enumerate(top_posts, 1):
        clean_caption = _strip_hashtags(post.caption)
        html_parts.append(f"<div style='margin-bottom: 30px;'>")
        if post.image_url:
            html_parts.append(f"<img src='{post.image_url}' style='width: 100%; border-radius: 8px; margin-bottom: 10px;'>")
        html_parts.append(f"<p style='font-size: 16px; line-height: 1.6;'>{clean_caption}</p>")
        html_parts.append(f"<p style='color: #999; font-size: 12px;'>📈 {post.engagement_rate:.1%} engagement · {post.pillar}</p>")
        html_parts.append(f"</div>")

    html_parts.append(f"<hr style='border: none; border-top: 1px solid #eee; margin: 20px 0;'>")
    html_parts.append(f"<p style='color: #999; font-size: 12px; text-align: center;'>")
    html_parts.append(f"Sent with care by {persona_name} · ")
    html_parts.append(f"<a href='https://instagram.com/aeloria' style='color: #666;'>Follow on Instagram</a>")
    html_parts.append(f"</p>")
    html_parts.append(f"</body></html>")

    html_body = "\n".join(html_parts)

    # Build plain text body
    text_parts = [f"{persona_name}'s Weekly Digest", "=" * 40, ""]
    for i, post in enumerate(top_posts, 1):
        clean_caption = _strip_hashtags(post.caption)
        text_parts.append(f"[{i}] {clean_caption}")
        text_parts.append(f"   📈 {post.engagement_rate:.1%} engagement · {post.pillar}")
        text_parts.append("")
    text_parts.append(f"Follow on Instagram: https://instagram.com/aeloria")

    text_body = "\n".join(text_parts)

    result = NewsletterResult(
        subject=subject,
        preheader=preheader,
        html_body=html_body,
        text_body=text_body,
        post_count=len(top_posts),
    )

    log.info("Newsletter generated: %d posts, subject='%s'", len(top_posts), subject[:50])
    return result