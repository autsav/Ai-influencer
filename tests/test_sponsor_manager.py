"""Tests for brand deal pipeline and sponsor management."""
import pytest
from aeloria.distribution.sponsor_manager import SponsorManager, SponsorDeal, RateCard


class TestCalculateRate:
    def setup_method(self):
        self.manager = SponsorManager()

    def test_basic_rate(self):
        rate = self.manager.calculate_rate(5000, 0.05, "static_post")
        # 5000/1000 * 8.0 CPM * (0.05/0.03) * 1.0 = 5 * 8 * 1.667 * 1 = 66.67
        assert rate > 0
        assert rate == pytest.approx(66.67, rel=0.1)

    def test_reel_costs_more_than_static(self):
        static = self.manager.calculate_rate(5000, 0.05, "static_post")
        reel = self.manager.calculate_rate(5000, 0.05, "reel")
        assert reel > static
        assert reel == pytest.approx(static * 2.0, rel=0.01)

    def test_story_costs_less(self):
        static = self.manager.calculate_rate(5000, 0.05, "static_post")
        story = self.manager.calculate_rate(5000, 0.05, "story")
        assert story < static
        assert story == pytest.approx(static * 0.5, rel=0.01)

    def test_higher_engagement_costs_more(self):
        low = self.manager.calculate_rate(5000, 0.02, "static_post")
        high = self.manager.calculate_rate(5000, 0.08, "static_post")
        assert high > low

    def test_more_followers_costs_more(self):
        small = self.manager.calculate_rate(1000, 0.05, "static_post")
        large = self.manager.calculate_rate(50000, 0.05, "static_post")
        assert large > small

    def test_engagement_floor(self):
        # Very low engagement should still have a floor
        rate = self.manager.calculate_rate(5000, 0.001, "static_post")
        assert rate > 0


class TestGenerateRateCard:
    def setup_method(self):
        self.manager = SponsorManager()

    def test_includes_all_post_types(self):
        card = self.manager.generate_rate_card(5000, 0.05)
        assert card.static_post_rate > 0
        assert card.carousel_rate > 0
        assert card.reel_rate > 0
        assert card.story_rate > 0
        assert card.bundle_rate > 0

    def test_bundle_cheaper_than_sum(self):
        card = self.manager.generate_rate_card(5000, 0.05)
        individual_sum = card.reel_rate + card.carousel_rate + (card.story_rate * 2)
        assert card.bundle_rate < individual_sum

    def test_includes_notes(self):
        card = self.manager.generate_rate_card(5000, 0.05)
        assert "5,000" in card.notes
        assert "5.0%" in card.notes


class TestGenerateMediaKit:
    def setup_method(self):
        self.manager = SponsorManager()

    def test_contains_audience_data(self):
        kit = self.manager.generate_media_kit(5000, 0.08, avg_reach=2000)
        assert kit["audience"]["followers"] == 5000
        assert kit["audience"]["avg_reach_per_post"] == 2000

    def test_contains_rate_card(self):
        kit = self.manager.generate_media_kit(5000, 0.08)
        assert "static_post" in kit["rate_card"]
        assert "reel" in kit["rate_card"]

    def test_contains_content_mix(self):
        kit = self.manager.generate_media_kit(5000, 0.08)
        assert "reels" in kit["content_mix"]
        assert "carousels" in kit["content_mix"]

    def test_custom_pillars(self):
        kit = self.manager.generate_media_kit(5000, 0.08, top_pillars=["AI tools", "Automation"])
        assert "AI tools" in kit["audience"]["top_pillars"]


class TestCreateDeal:
    def test_creates_with_id(self):
        manager = SponsorManager()
        deal = manager.create_deal("Acme Corp", "contact@acme.com", "reel")
        assert deal.deal_id
        assert "acme" in deal.deal_id.lower()

    def test_default_status_prospect(self):
        manager = SponsorManager()
        deal = manager.create_deal("Brand", "email@brand.com")
        assert deal.status == "prospect"

    def test_has_timestamp(self):
        manager = SponsorManager()
        deal = manager.create_deal("Brand", "email@brand.com")
        assert deal.created_at  # non-empty