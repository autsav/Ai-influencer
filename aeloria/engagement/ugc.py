"""UGC / mention tracking — track brand mentions and repost UGC.

Monitors Instagram comments, mentions, and tags for user-generated content.
Enables community building by tracking and responding to UGC.

Usage:
    from aeloria.engagement.ugc import UGCTracker, UGCEntry
    tracker = UGCTracker(db, settings)
    mentions = tracker.get_mentions()
    for m in mentions:
        print(f"@{m.username} mentioned us: {m.text[:50]}")
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import Counter

log = logging.getLogger(__name__)


@dataclass
class UGCEntry:
    """A user-generated content mention or tag."""
    entry_id: str = ""
    username: str = ""
    platform: str = "instagram"
    type: str = "mention"  # "mention", "tag", "comment", "repost"
    text: str = ""
    media_url: str | None = None
    permalink: str = ""
    timestamp: str = ""
    sentiment: str = "neutral"  # "positive", "negative", "neutral"
    responded: bool = False
    reposted: bool = False

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.entry_id:
            self.entry_id = f"{self.platform}-{self.username}-{self.timestamp[:10]}"


class UGCTracker:
    """Track mentions, tags, and UGC across platforms.

    Provides methods to fetch, classify, and manage UGC entries.
    In production, connects to IG Graph API webhooks for real-time mentions.
    """

    def __init__(self, db=None, settings=None):
        self.db = db
        self.settings = settings
        self.our_username = getattr(settings, "our_username", "aeloria")

    def get_mentions(self, limit: int = 50) -> list[UGCEntry]:
        """Get recent mentions from the database.

        Returns UGCEntry objects for mentions, tags, and comments referencing us.
        """
        if not self.db:
            return []

        try:
            rows = self.db.select_all("ugc_mentions") or []
            entries = []
            for r in rows[:limit]:
                entries.append(UGCEntry(
                    entry_id=r.get("id", ""),
                    username=r.get("username", ""),
                    platform=r.get("platform", "instagram"),
                    type=r.get("type", "mention"),
                    text=r.get("text", ""),
                    media_url=r.get("media_url"),
                    permalink=r.get("permalink", ""),
                    timestamp=r.get("timestamp", ""),
                    sentiment=r.get("sentiment", "neutral"),
                    responded=r.get("responded", False),
                    reposted=r.get("reposted", False),
                ))
            return entries
        except Exception as e:
            log.warning("Failed to fetch UGC mentions: %s", e)
            return []

    def classify_sentiment(self, text: str) -> str:
        """Simple lexicon-based sentiment classification for UGC."""
        text_lower = text.lower()
        positive = any(w in text_lower for w in
                       ["love", "amazing", "great", "awesome", "inspiring", "helpful",
                        "thanks", "🔥", "❤️", "👍", "👏", "💯"])
        negative = any(w in text_lower for w in
                       ["hate", "terrible", "bad", "fake", "scam", "👎", "😡"])

        if positive and not negative:
            return "positive"
        if negative and not positive:
            return "negative"
        return "neutral"

    def get_top_advocates(self, entries: list[UGCEntry], top_n: int = 10) -> list[tuple[str, int]]:
        """Identify users who mention us most frequently (brand advocates).

        Returns list of (username, mention_count) sorted by count.
        """
        counter = Counter(e.username for e in entries if e.username)
        return counter.most_common(top_n)

    def get_unresponded(self, entries: list[UGCEntry] | None = None) -> list[UGCEntry]:
        """Filter to entries that haven't been responded to yet."""
        if entries is None:
            entries = self.get_mentions()
        return [e for e in entries if not e.responded]

    def get_repostable(self, entries: list[UGCEntry] | None = None) -> list[UGCEntry]:
        """Filter to positive UGC entries that are repostable.

        Criteria: positive sentiment, has media, not already reposted.
        """
        if entries is None:
            entries = self.get_mentions()
        return [
            e for e in entries
            if e.sentiment == "positive" and e.media_url and not e.reposted
        ]

    def generate_response(self, entry: UGCEntry) -> str:
        """Generate a response to a UGC mention.

        Simple template-based responses. In production, route through LLM.
        """
        if entry.sentiment == "positive":
            return f"Thank you @{entry.username}! So glad you found this helpful 💜"
        elif entry.sentiment == "negative":
            return f"Hey @{entry.username}, sorry to hear that. Could you DM us with more details?"
        else:
            return f"Thanks for the mention @{entry.username}! 🙌"

    def stats(self, entries: list[UGCEntry] | None = None) -> dict:
        """Get summary statistics for UGC entries."""
        if entries is None:
            entries = self.get_mentions()

        if not entries:
            return {"total": 0, "positive": 0, "negative": 0, "neutral": 0,
                    "unresponded": 0, "reposted": 0, "top_advocates": []}

        return {
            "total": len(entries),
            "positive": sum(1 for e in entries if e.sentiment == "positive"),
            "negative": sum(1 for e in entries if e.sentiment == "negative"),
            "neutral": sum(1 for e in entries if e.sentiment == "neutral"),
            "unresponded": sum(1 for e in entries if not e.responded),
            "reposted": sum(1 for e in entries if e.reposted),
            "top_advocates": self.get_top_advocates(entries),
        }