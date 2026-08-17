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
from datetime import datetime, timezone, timedelta
from collections import Counter

from aeloria.analytics.competitor_scraper import CompetitorScraper, ScrapedProfile

log = logging.getLogger(__name__)

# How far back to look when computing growth_rate from the snapshot history.
GROWTH_WINDOW_DAYS = 7
# Hard ceiling on growth_rate (fraction/week). Above this we treat as noise /
# a one-off viral spike and clamp, so a single breakout post doesn't break
# the bounded strategy-weight update downstream.
GROWTH_RATE_CAP = 0.50


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

    def __init__(self, db, settings, scraper: CompetitorScraper | None = None):
        self.db = db
        self.settings = settings
        self.competitor_usernames = getattr(settings, "competitor_usernames", [])
        self.our_username = getattr(settings, "our_username", "aeloria")
        # Optional scraper injection; if None, scrape_*() is a no-op.
        self.scraper = scraper if scraper is not None else CompetitorScraper()

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

    # ── Live data plumbing (wired by run_competitor_pending on the Sunday cron) ──

    def scrape_and_store(self, usernames: list[str] | None = None) -> int:
        """Hit Apify, persist each result to `competitor_profiles` as the
        current snapshot. Returns the number of profiles written. Scraping
        failures are swallowed (the scraper logs them); a 0 return is a valid
        outcome (token missing, network down, Apify 5xx)."""
        targets = usernames or self.competitor_usernames
        if not targets:
            return 0
        scraped = self.scraper.scrape_usernames(targets)
        written = 0
        for profile in scraped:
            try:
                self._upsert_snapshot(profile)
                written += 1
            except Exception as exc:
                log.error("upsert snapshot failed for %s: %s", profile.username, exc)
        log.info("scrape_and_store: %d/%d profiles written", written, len(targets))
        return written

    def _upsert_snapshot(self, profile: ScrapedProfile) -> None:
        """Upsert today's snapshot row. A re-scrape on the same day overwrites
        the day's row (so a transient Apify failure doesn't poison the
        snapshot); a scrape on a new day writes a new row (so growth_rate
        has history). Implemented as a server-side ON CONFLICT upsert against
        the unique (username, captured_on) index, so duplicate-key collisions
        never surface as exceptions to the cron loop."""
        row = {
            "username": profile.username,
            "display_name": profile.full_name,
            "follower_count": profile.followers,
            "following_count": profile.follows_count,
            "post_count": profile.posts_count,
            "biography": profile.biography,
            "is_verified": profile.is_verified,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self.db._client.table("competitor_profiles").upsert(
                row,
                on_conflict="username,captured_on",
            ).execute()
        except AttributeError:
            # Older supabase-py without upsert() — fall back to insert+catch
            # (the previous behaviour, retained for backwards compatibility).
            try:
                self.db.insert("competitor_profiles", row)
            except Exception as exc:
                msg = str(exc).lower()
                if "duplicate" in msg or "unique" in msg:
                    self.db._client.table("competitor_profiles").update({
                        "display_name": profile.full_name,
                        "follower_count": profile.followers,
                        "following_count": profile.follows_count,
                        "post_count": profile.posts_count,
                        "biography": profile.biography,
                        "is_verified": profile.is_verified,
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                    }).eq("username", profile.username).execute()
                    return
                raise

    def compute_growth_rate(self, username: str, followers: int) -> float:
        """Weekly follower growth as a fraction (e.g. 0.05 = +5%/wk). Returns
        0.0 when there's no history yet — first scrape has no comparison
        point, and we'd rather under-report growth than invent it."""
        if followers <= 0:
            return 0.0
        cutoff = (datetime.now(timezone.utc) - timedelta(days=GROWTH_WINDOW_DAYS)).isoformat()
        try:
            history = (
                self.db._client.table("competitor_profiles")
                .select("follower_count, captured_at")
                .eq("username", username)
                .lt("captured_at", cutoff)
                .order("captured_at", desc=True).limit(1).execute().data
            )
        except Exception as exc:
            log.error("compute_growth_rate db read failed for %s: %s", username, exc)
            return 0.0
        if not history:
            return 0.0
        prior = int(history[0].get("follower_count") or 0)
        if prior <= 0:
            return 0.0
        rate = (followers - prior) / prior
        # Cap at +/- GROWTH_RATE_CAP. Negative rates are also possible
        # (audit-block, mass-unfollow); we don't clamp those — losing 30%
        # is genuinely useful signal that downstream weights should react to.
        return max(min(rate, GROWTH_RATE_CAP), -GROWTH_RATE_CAP)

    def refresh_growth_rates(self) -> int:
        """Walk every stored profile and refresh its growth_rate column using
        the current follower_count vs. the snapshot GROWTH_WINDOW_DAYS ago.
        Idempotent; safe to run weekly."""
        try:
            rows = self.db._client.table("competitor_profiles").select(
                "username, follower_count"
            ).execute().data
        except Exception as exc:
            log.error("refresh_growth_rates read failed: %s", exc)
            return 0
        updated = 0
        seen: set[str] = set()
        for row in rows or []:
            username = row.get("username")
            followers = int(row.get("follower_count") or 0)
            if not username or username in seen:
                continue
            seen.add(username)
            rate = self.compute_growth_rate(username, followers)
            try:
                self.db._client.table("competitor_profiles").update({
                    "growth_rate": rate,
                }).eq("username", username).execute()
                updated += 1
            except Exception as exc:
                log.error("growth_rate update failed for %s: %s", username, exc)
        log.info("refresh_growth_rates: %d/%d profiles updated", updated, len(seen))
        return updated

    def has_competitor_snapshot_today(self) -> bool:
        """Gate: the weekly cron should scrape at most once per day."""
        try:
            today_start = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00+00:00")
            rows = (
                self.db._client.table("competitor_profiles")
                .select("id").gte("captured_at", today_start).limit(1).execute().data
            )
            return bool(rows)
        except Exception:
            return False


def run_competitor_pending(db, settings, tg=None) -> int:
    """Scheduled job: scrape competitors + refresh growth rates + emit a
    short Telegram summary. Best-effort: any single step failing logs and
    returns 0 (the next weekly run retries)."""
    try:
        tracker = CompetitorTracker(db, settings)
        if tracker.has_competitor_snapshot_today():
            log.info("competitor snapshot already captured today — skipping")
            return 0
        n_written = tracker.scrape_and_store()
        n_growth = tracker.refresh_growth_rates()
        if tg and n_written:
            tg.send_message(
                f"🔍 Competitors: scraped {n_written}, growth refreshed on {n_growth}"
            )
        return n_written
    except Exception as exc:
        log.error("run_competitor_pending failed: %s", exc)
        return 0