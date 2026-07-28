"""Brand deal pipeline — sponsor CRM, media kit generation, rate card calculator.

Manages brand sponsorship deals from outreach to delivery. Auto-generates
media kits from analytics data and calculates rate cards based on reach
and engagement.

Usage:
    from aeloria.distribution.sponsor_manager import SponsorManager, SponsorDeal, RateCard
    manager = SponsorManager(db, settings)
    rate = manager.calculate_rate(followers=5000, engagement_rate=0.08, post_type="reel")
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

log = logging.getLogger(__name__)


@dataclass
class SponsorDeal:
    """A brand sponsorship deal."""
    deal_id: str = ""
    brand_name: str = ""
    contact_email: str = ""
    contact_name: str = ""
    deal_type: str = "single_post"  # "single_post", "carousel", "reel", "story", "multi_post"
    post_count: int = 1
    agreed_price: float = 0.0
    status: str = "prospect"  # "prospect", "outreach", "negotiating", "confirmed", "delivered", "paid"
    brief: str = ""
    deliverables: list[str] = field(default_factory=list)
    created_at: str = ""
    deadline: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.deal_id:
            self.deal_id = f"deal-{self.brand_name[:10].lower().replace(' ', '-')}-{self.created_at[:10]}"


@dataclass
class RateCard:
    """Calculated rate card for sponsorship pricing."""
    followers: int = 0
    engagement_rate: float = 0.0
    # Per-post rates
    static_post_rate: float = 0.0
    carousel_rate: float = 0.0
    reel_rate: float = 0.0
    story_rate: float = 0.0
    # Package rates
    multi_post_discount: float = 0.15  # 15% off for 3+ posts
    bundle_rate: float = 0.0  # all-in-one package
    notes: str = ""


class SponsorManager:
    """Manage brand sponsorship deals and rate cards.

    Rate calculation follows industry-standard formulas:
    - Base rate = followers / 1000 * CPM_rate
    - Engagement multiplier = engagement_rate / 0.03 (normalized to 3% baseline)
    - Post type multiplier: reel > carousel > static > story
    """

    # CPM (cost per mille) rates by follower tier
    CPM_TIERS = [
        {"min_followers": 0, "cpm": 5.0},
        {"min_followers": 1000, "cpm": 8.0},
        {"min_followers": 10000, "cpm": 12.0},
        {"min_followers": 50000, "cpm": 15.0},
        {"min_followers": 100000, "cpm": 20.0},
    ]

    # Post type multipliers (relative to static post)
    POST_TYPE_MULTIPLIERS = {
        "static_post": 1.0,
        "carousel": 1.5,
        "reel": 2.0,
        "story": 0.5,
        "multi_post": 2.5,
    }

    def __init__(self, db=None, settings=None):
        self.db = db
        self.settings = settings

    def _get_cpm(self, followers: int) -> float:
        """Get CPM rate based on follower count."""
        cpm = self.CPM_TIERS[0]["cpm"]
        for tier in self.CPM_TIERS:
            if followers >= tier["min_followers"]:
                cpm = tier["cpm"]
        return cpm

    def calculate_rate(self, followers: int, engagement_rate: float,
                       post_type: str = "static_post") -> float:
        """Calculate sponsorship rate for a single post.

        Formula: (followers / 1000) * CPM * engagement_multiplier * post_type_multiplier

        Args:
            followers: Follower count
            engagement_rate: Engagement rate (0.0-1.0)
            post_type: "static_post", "carousel", "reel", "story", "multi_post"

        Returns:
            Recommended price in USD
        """
        cpm = self._get_cpm(followers)
        base_rate = (followers / 1000) * cpm

        # Engagement multiplier: normalize to 3% baseline
        engagement_multiplier = max(engagement_rate / 0.03, 0.5)  # floor at 0.5x

        # Post type multiplier
        type_multiplier = self.POST_TYPE_MULTIPLIERS.get(post_type, 1.0)

        rate = base_rate * engagement_multiplier * type_multiplier
        return round(rate, 2)

    def generate_rate_card(self, followers: int, engagement_rate: float) -> RateCard:
        """Generate a full rate card across all post types.

        Args:
            followers: Current follower count
            engagement_rate: Current engagement rate (0.0-1.0)

        Returns:
            RateCard with per-post and bundle pricing
        """
        static = self.calculate_rate(followers, engagement_rate, "static_post")
        carousel = self.calculate_rate(followers, engagement_rate, "carousel")
        reel = self.calculate_rate(followers, engagement_rate, "reel")
        story = self.calculate_rate(followers, engagement_rate, "story")

        # Bundle: 1 reel + 1 carousel + 2 stories
        bundle = reel + carousel + (story * 2)
        bundle *= (1 - 0.10)  # 10% bundle discount

        return RateCard(
            followers=followers,
            engagement_rate=engagement_rate,
            static_post_rate=static,
            carousel_rate=carousel,
            reel_rate=reel,
            story_rate=story,
            bundle_rate=round(bundle, 2),
            notes=f"Based on {followers:,} followers at {engagement_rate:.1%} engagement",
        )

    def generate_media_kit(self, followers: int, engagement_rate: float,
                           avg_reach: int = 0, top_pillars: list[str] | None = None,
                           persona_name: str = "Aeloria") -> dict:
        """Generate a media kit dict from analytics data.

        Returns a dict suitable for JSON export or PDF generation.
        """
        rate_card = self.generate_rate_card(followers, engagement_rate)

        return {
            "persona": persona_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "audience": {
                "followers": followers,
                "engagement_rate": f"{engagement_rate:.1%}",
                "avg_reach_per_post": avg_reach,
                "top_pillars": top_pillars or ["AI automation", "AI tools", "Founder lifestyle"],
            },
            "content_mix": {
                "reels": "30%",
                "carousels": "30%",
                "static_posts": "30%",
                "stories": "10%",
            },
            "rate_card": {
                "static_post": f"${rate_card.static_post_rate}",
                "carousel": f"${rate_card.carousel_rate}",
                "reel": f"${rate_card.reel_rate}",
                "story": f"${rate_card.story_rate}",
                "bundle": f"${rate_card.bundle_rate}",
            },
            "contact": "partnerships@aeloria.ai",
        }

    def create_deal(self, brand_name: str, contact_email: str,
                    deal_type: str = "single_post", post_count: int = 1,
                    deadline: str = "") -> SponsorDeal:
        """Create a new sponsorship deal record."""
        deal = SponsorDeal(
            brand_name=brand_name,
            contact_email=contact_email,
            deal_type=deal_type,
            post_count=post_count,
            deadline=deadline,
        )
        log.info("Created deal: %s for %s (%s)", deal.deal_id, brand_name, deal_type)
        return deal

    def get_deals_by_status(self, status: str) -> list[SponsorDeal]:
        """Get all deals at a given status."""
        if not self.db:
            return []
        try:
            rows = self.db.select("sponsor_deals", {"status": status}) or []
            return [
                SponsorDeal(
                    deal_id=r.get("id", ""),
                    brand_name=r.get("brand_name", ""),
                    contact_email=r.get("contact_email", ""),
                    deal_type=r.get("deal_type", "single_post"),
                    post_count=r.get("post_count", 1),
                    agreed_price=r.get("agreed_price", 0.0),
                    status=r.get("status", status),
                )
                for r in rows
            ]
        except Exception as e:
            log.warning("Failed to fetch deals: %s", e)
            return []