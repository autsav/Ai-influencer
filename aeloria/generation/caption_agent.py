"""
Caption Agent — multi-agent pipeline content creator.

Adapted from agency-agents/marketing-content-creator.md.

Generates platform-native captions:
  - Feed posts: 50-300 words, hook → body → CTA
  - Reels: 20-80 words, hook matches script caption_prefix
  - Stories: punchy 1-2 lines

Hashtag sets: 3 large + 3 medium + 3 niche + 1 branded.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class FeedCaption:
    hook: str           # First 2 lines, standalone
    body: str           # Value delivery, 2-4 sentences
    cta: str            # Specific action request


@dataclass
class ReelsCaption:
    hook: str
    body: str


@dataclass
class StoryCaption:
    line: str
    context: str


@dataclass
class HashtagSet:
    large: list[str]
    medium: list[str]
    niche: list[str]
    branded: list[str]


@dataclass
class CaptionResult:
    feed_caption: FeedCaption
    reels_caption: ReelsCaption
    story_caption: StoryCaption
    hashtag_set: HashtagSet
    engagement_score_prediction: float
    posting_time_recommendation: str

    def to_dict(self) -> dict:
        d = {
            "feed_caption": self.feed_caption.__dict__,
            "reels_caption": self.reels_caption.__dict__,
            "story_caption": self.story_caption.__dict__,
            "hashtag_set": self.hashtag_set.__dict__,
            "engagement_score_prediction": self.engagement_score_prediction,
            "posting_time_recommendation": self.posting_time_recommendation,
        }
        return d


HOOK_TEMPLATES_BY_PILLAR = {
    "AI tools + productivity": [
        "This AI tool saved me 20 hours last week.",
        "I deleted 5 apps after testing these AI workflows.",
        "The cheapest productivity hack isn't on your screen.",
        "Stop using AI tools like this.",
    ],
    "Lifestyle / city / travel": [
        "Sunday morning ritual, no exceptions.",
        "Three places every city person should know.",
        "How I made Sunday feel like a vacation.",
        "The cafe that changed my whole week.",
    ],
    "Founder journey / hustle": [
        "Building in public taught me one thing.",
        "I almost quit last month. Here's why I didn't.",
        "Day 1 vs day 90 of building solo.",
        "What nobody tells you about the first $1000.",
    ],
    "Trends / pop culture": [
        "Everyone's talking about this. Here's the real take.",
        "Three trends I tried. Two flopped. One exploded.",
        "The trend nobody predicted this week.",
        "Trying the trend before it goes mainstream.",
    ],
    "Authentic day-in-the-life": [
        "What my morning actually looks like.",
        "Real hours. Real coffee. No filter.",
        "How I structure a day when nothing goes to plan.",
        "Behind the scenes: 6am to 6pm.",
    ],
}


BODY_TEMPLATES = [
    "I tried it for 30 days. The result changed everything.",
    "Most people overcomplicate this. Here's the simple version.",
    "Three reasons this works. First — speed. Second — focus. Third — sanity.",
    "The math: 2 hours saved per day × 30 days = a full work week back.",
    "Tried it Monday. By Wednesday the result was obvious.",
]

CTA_TEMPLATES = [
    "Save this. Try it for a week. Watch what happens.",
    "Comment which one you'll try first.",
    "Tag someone who needs to hear this.",
    "DM me your results — I read every one.",
    "Follow for more tested workflows, not recycled advice.",
    "Share to your story if this hit.",
]


class CaptionAgent:
    """Generates platform-native captions for the young_energetic persona."""

    def __init__(self, persona_name: str = "young_energetic"):
        self.persona_name = persona_name
        self.branded_tag = "#YoungEnergeticAI"

    def create_caption(
        self,
        hook_type: str = "curiosity_gap",
        caption_prefix: str = "",
        content_pillar: str = "AI tools + productivity",
        trending_hashtags: Optional[list[str]] = None,
        topic: str = "",
    ) -> CaptionResult:
        """Build full caption package (feed + reels + story + hashtags)."""

        hooks = HOOK_TEMPLATES_BY_PILLAR.get(content_pillar, HOOK_TEMPLATES_BY_PILLAR["AI tools + productivity"])
        hook_line = caption_prefix or random.choice(hooks)

        feed_hook = hook_line
        feed_body = random.choice(BODY_TEMPLATES)
        feed_cta = random.choice(CTA_TEMPLATES)

        feed_caption = FeedCaption(hook=feed_hook, body=feed_body, cta=feed_cta)

        reels_caption = ReelsCaption(
            hook=hook_line,
            body="Save this. Follow for more.",
        )

        story_caption = StoryCaption(
            line=hook_line[:80],
            context="Tap to read more.",
        )

        # Hashtag selection: rotate, mix sizes, branded
        trending = trending_hashtags or []
        large_tags = self._pick_large(content_pillar, trending)
        medium_tags = self._pick_medium(content_pillar)
        niche_tags = self._pick_niche(content_pillar)
        hashtag_set = HashtagSet(
            large=large_tags,
            medium=medium_tags,
            niche=niche_tags,
            branded=[self.branded_tag, "#AIFounder"],
        )

        # Engagement score prediction (heuristic)
        engagement_score = self._predict_engagement(hook_type, content_pillar, len(hashtag_set.large + hashtag_set.medium))

        # Posting time (will be overridden by DistributionScheduler if learnings exist)
        posting_time = self._recommend_posting_time(content_pillar)

        return CaptionResult(
            feed_caption=feed_caption,
            reels_caption=reels_caption,
            story_caption=story_caption,
            hashtag_set=hashtag_set,
            engagement_score_prediction=engagement_score,
            posting_time_recommendation=posting_time,
        )

    def _pick_large(self, pillar: str, trending: list[str]) -> list[str]:
        """Pick 3 large hashtags (>1M posts)."""
        large_pool = {
            "AI tools + productivity": ["#productivity", "#aitools", "#workhacks"],
            "Lifestyle / city / travel": ["#lifestyle", "#citylife", "#weekendvibes"],
            "Founder journey / hustle": ["#startup", "#entrepreneur", "#buildingabrand"],
            "Trends / pop culture": ["#trending", "#popculture", "#viral"],
            "Authentic day-in-the-life": ["#dayinmylife", "#reallife", "#morningroutine"],
        }
        pool = large_pool.get(pillar, large_pool["AI tools + productivity"])
        # Use up to 2 trending if provided
        picks = (trending[:2] if trending else []) + pool[:3]
        return picks[:3]

    def _pick_medium(self, pillar: str) -> list[str]:
        medium_pool = {
            "AI tools + productivity": ["#aiworkflow", "#chatgptips", "#productivityhacks"],
            "Lifestyle / city / travel": ["#coffeelover", "#cityvibes", "#sundayritual"],
            "Founder journey / hustle": ["#solofounder", "#buildinginpublic", "#startuplife"],
            "Trends / pop culture": ["#trendwatch", "#viralreels", "#culture"],
            "Authentic day-in-the-life": ["#6amclub", "#morningroutine", "#everydaymoments"],
        }
        return medium_pool.get(pillar, medium_pool["AI tools + productivity"])[:3]

    def _pick_niche(self, pillar: str) -> list[str]:
        niche_pool = {
            "AI tools + productivity": ["#aihustle", "#aioperators", "#toolstack"],
            "Lifestyle / city / travel": ["#thirdwavecoffee", "#urbanminimalist", "#slowmornings"],
            "Founder journey / hustle": ["#bootstrapper", "#day90", "#first1kdollars"],
            "Trends / pop culture": ["#trenddeconstruction", "#trendreview"],
            "Authentic day-in-the-life": ["#realhours", "#noscrollmorning", "#actualmorning"],
        }
        return niche_pool.get(pillar, niche_pool["AI tools + productivity"])[:3]

    def _predict_engagement(self, hook_type: str, pillar: str, hashtag_count: int) -> float:
        score = 0.04  # baseline IG engagement ~4%
        if hook_type == "relatable_pain":
            score += 0.025
        elif hook_type == "curiosity_gap":
            score += 0.020
        elif hook_type == "pattern_interrupt":
            score += 0.015
        if pillar in ["AI tools + productivity", "Founder journey / hustle"]:
            score += 0.015
        # Hashtag count sweet spot 6-9
        if 6 <= hashtag_count <= 9:
            score += 0.005
        return round(min(score, 0.12), 4)

    def _recommend_posting_time(self, pillar: str) -> str:
        # Heuristic — overridden by DistributionScheduler if learnings.json has data
        times = {
            "AI tools + productivity": "08:00",
            "Lifestyle / city / travel": "12:00",
            "Founder journey / hustle": "18:00",
            "Trends / pop culture": "20:00",
            "Authentic day-in-the-life": "07:00",
        }
        return times.get(pillar, "12:00")

    def to_json(self, result: CaptionResult) -> str:
        import json
        return json.dumps(result.to_dict(), indent=2)
