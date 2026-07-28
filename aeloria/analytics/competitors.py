"""Competitor benchmarking — track competitor influencers and find content gaps.

Monitors 5-10 competitor accounts, tracks their growth rate, top posts,
and content patterns. Generates a weekly report highlighting opportunities
we can exploit.

Usage:
    from aeloria.analytics.competitors import CompetitorTracker, CompetitorReport
    tracker = CompetitorTracker(db, settings)
    report = tracker.generate_report()
    print(f"Top competitor: {report.top_competitor}")
    print(f"Content gaps: {report.content_gaps}")
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import Counter

log = logging.getLogger(__name__)


@dataclass
class CompetitorProfile:
    """A tracked competitor influencer."""
    username: str
    display_name: str = ""
    follower_count: int = 0
    following_count: int = 0
    post_count: int = 0
    avg_engagement_rate: float = 0.0
    top_pillars: list[str] = field(default_factory=list)
    posting_frequency: float = 0.0  # posts per week
    growth_rate: float = 0.0  # follower growth % per week
    notes: str = ""


@dataclass
class CompetitorReport:
    """Weekly competitor benchmarking report."""
    generated_at: str = ""
    competitors: list[CompetitorProfile] = field(default_factory=list)
    top_competitor: str = ""  # username of highest growth
    avg_competitor_engagement: float = 0.0
    content_gaps: list[str] = field(default_factory=list)
    content_overlaps: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    our_followers: int = 0
    our_engagement_rate: float = 0.0

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()


class CompetitorTracker:
    """Track and benchmark competitor influencers.

    Configurable via settings:
    - competitor_usernames: list of competitor IG usernames to track
    - our_username: our IG username for comparison
    """

    def __init__(self, db, settings):
        self.db = db
        self.settings = settings
        self.competitor_usernames = getattr(settings, "competitor_usernames", [])
        self.our_username = getattr(settings, "our_username", "aeloria")

    def _fetch_competitor_profile(self, username: str) -> CompetitorProfile:
        """Fetch a competitor's profile data from IG Graph API or DB.

        In production, this calls the IG Graph API. For now, returns a stub
        that can be populated from the DB or manual entry.
        """
        try:
            rows = self.db.select("competitor_profiles", {"username": username}, limit=1)
            if rows:
                r = rows[0]
                return CompetitorProfile(
                    username=r.get("username", username),
                    display_name=r.get("display_name", ""),
                    follower_count=r.get("follower_count", 0),
                    following_count=r.get("following_count", 0),
                    post_count=r.get("post_count", 0),
                    avg_engagement_rate=r.get("avg_engagement_rate", 0.0),
                    top_pillars=r.get("top_pillars", []),
                    posting_frequency=r.get("posting_frequency", 0.0),
                    growth_rate=r.get("growth_rate", 0.0),
                )
        except Exception:
            pass

        return CompetitorProfile(username=username)

    def _get_our_metrics(self) -> tuple[int, float]:
        """Get our follower count and engagement rate."""
        try:
            followers = self.db.current_follower_count()
            # Get our avg engagement from recent posts
            posts = self.db.select_all("post_metrics") or []
            if posts:
                rates = []
                for p in posts:
                    reach = p.get("reach", 0)
                    if reach > 0:
                        rate = (p.get("likes", 0) + p.get("comments", 0) +
                               p.get("shares", 0) + p.get("saves", 0)) / reach
                        rates.append(rate)
                avg_rate = sum(rates) / len(rates) if rates else 0.0
                return followers, avg_rate
            return followers, 0.0
        except Exception:
            return 0, 0.0

    def _identify_content_gaps(self, competitors: list[CompetitorProfile],
                                our_pillars: list[str]) -> list[str]:
        """Find content pillars competitors cover that we don't."""
        competitor_pillars = set()
        for c in competitors:
            competitor_pillars.update(c.top_pillars)

        our_set = set(our_pillars)
        gaps = competitor_pillars - our_set
        return sorted(gaps)

    def _identify_overlaps(self, competitors: list[CompetitorProfile],
                           our_pillars: list[str]) -> list[str]:
        """Find content pillars we share with competitors."""
        competitor_pillars = set()
        for c in competitors:
            competitor_pillars.update(c.top_pillars)

        our_set = set(our_pillars)
        overlaps = competitor_pillars & our_set
        return sorted(overlaps)

    def _generate_recommendations(self, competitors: list[CompetitorProfile],
                                  gaps: list[str], our_followers: int,
                                  our_engagement: float) -> list[str]:
        """Generate actionable recommendations from the benchmark data."""
        recs = []

        # Content gap recommendations
        if gaps:
            recs.append(f"Content gap: competitors cover {', '.join(gaps[:3])} — consider adding these pillars")

        # Growth comparison
        for c in competitors:
            if c.growth_rate > 0 and c.follower_count > our_followers:
                recs.append(f"{c.username} growing at {c.growth_rate:.1%}/wk with {c.follower_count:,} followers — study their top content")

        # Engagement comparison
        avg_comp_engagement = sum(c.avg_engagement_rate for c in competitors) / len(competitors) if competitors else 0
        if our_engagement < avg_comp_engagement * 0.5:
            recs.append(f"Our engagement ({our_engagement:.1%}) is below competitor avg ({avg_comp_engagement:.1%}) — review content quality")
        elif our_engagement > avg_comp_engagement * 1.5:
            recs.append(f"Our engagement ({our_engagement:.1%}) exceeds competitor avg ({avg_comp_engagement:.1%}) — double down on current strategy")

        # Posting frequency
        for c in competitors:
            if c.posting_frequency > 0:
                recs.append(f"{c.username} posts {c.posting_frequency:.1f}x/week — {'we should match' if c.posting_frequency > 5 else 'similar to our cadence'}")

        return recs[:10]  # limit to top 10

    def generate_report(self, our_pillars: list[str] | None = None) -> CompetitorReport:
        """Generate a weekly competitor benchmarking report.

        Args:
            our_pillars: Our content pillars for gap analysis. Defaults to
                        standard Aeloria pillars if not provided.

        Returns:
            CompetitorReport with profiles, gaps, overlaps, and recommendations
        """
        if our_pillars is None:
            our_pillars = ["ai_workflows", "ai_tools", "case_studies",
                          "founder_lifestyle", "future_of_business"]

        # Fetch all competitor profiles
        competitors = []
        for username in self.competitor_usernames:
            profile = self._fetch_competitor_profile(username)
            competitors.append(profile)

        if not competitors:
            log.info("No competitors configured — returning empty report")
            return CompetitorReport()

        # Get our metrics
        our_followers, our_engagement = self._get_our_metrics()

        # Find top competitor by growth
        top = max(competitors, key=lambda c: c.growth_rate) if competitors else None

        # Identify gaps and overlaps
        gaps = self._identify_content_gaps(competitors, our_pillars)
        overlaps = self._identify_overlaps(competitors, our_pillars)

        # Calculate average competitor engagement
        avg_engagement = sum(c.avg_engagement_rate for c in competitors) / len(competitors)

        # Generate recommendations
        recs = self._generate_recommendations(
            competitors, gaps, our_followers, our_engagement
        )

        report = CompetitorReport(
            competitors=competitors,
            top_competitor=top.username if top else "",
            avg_competitor_engagement=avg_engagement,
            content_gaps=gaps,
            content_overlaps=overlaps,
            recommended_actions=recs,
            our_followers=our_followers,
            our_engagement_rate=our_engagement,
        )

        log.info(
            "Competitor report: %d competitors, %d gaps, %d overlaps, %d recommendations",
            len(competitors), len(gaps), len(overlaps), len(recs),
        )
        return report