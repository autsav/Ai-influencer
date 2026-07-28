"""Tests for UGC / mention tracking."""
import pytest
from unittest.mock import MagicMock
from aeloria.engagement.ugc import UGCTracker, UGCEntry


def _make_entry(username="user1", sentiment="neutral", text="Test",
                media_url=None, responded=False, reposted=False):
    return UGCEntry(
        username=username,
        sentiment=sentiment,
        text=text,
        media_url=media_url,
        responded=responded,
        reposted=reposted,
    )


class TestClassifySentiment:
    def setup_method(self):
        self.tracker = UGCTracker()

    def test_positive(self):
        assert self.tracker.classify_sentiment("Love this content! Amazing 🔥") == "positive"

    def test_negative(self):
        assert self.tracker.classify_sentiment("This is terrible and fake") == "negative"

    def test_neutral(self):
        assert self.tracker.classify_sentiment("Just a comment") == "neutral"

    def test_mixed_is_neutral(self):
        assert self.tracker.classify_sentiment("love it but also hate it") == "neutral"


class TestGetTopAdvocates:
    def test_counts_mentions(self):
        tracker = UGCTracker()
        entries = [
            _make_entry(username="alice"),
            _make_entry(username="alice"),
            _make_entry(username="alice"),
            _make_entry(username="bob"),
        ]
        advocates = tracker.get_top_advocates(entries)
        assert advocates[0] == ("alice", 3)
        assert advocates[1] == ("bob", 1)

    def test_empty(self):
        tracker = UGCTracker()
        assert tracker.get_top_advocates([]) == []


class TestGetUnresponded:
    def test_filters_responded(self):
        tracker = UGCTracker()
        entries = [
            _make_entry(username="a", responded=True),
            _make_entry(username="b", responded=False),
            _make_entry(username="c", responded=False),
        ]
        unresponded = tracker.get_unresponded(entries)
        assert len(unresponded) == 2
        assert all(not e.responded for e in unresponded)


class TestGetRepostable:
    def test_filters_positive_with_media(self):
        tracker = UGCTracker()
        entries = [
            _make_entry(username="a", sentiment="positive", media_url="https://img.jpg"),
            _make_entry(username="b", sentiment="positive", media_url=None),  # no media
            _make_entry(username="c", sentiment="negative", media_url="https://img.jpg"),  # negative
            _make_entry(username="d", sentiment="positive", media_url="https://img.jpg", reposted=True),  # already reposted
        ]
        repostable = tracker.get_repostable(entries)
        assert len(repostable) == 1
        assert repostable[0].username == "a"


class TestGenerateResponse:
    def test_positive_response(self):
        tracker = UGCTracker()
        entry = _make_entry(username="fan1", sentiment="positive")
        response = tracker.generate_response(entry)
        assert "fan1" in response
        assert "Thank" in response or "glad" in response

    def test_negative_response(self):
        tracker = UGCTracker()
        entry = _make_entry(username="unhappy", sentiment="negative")
        response = tracker.generate_response(entry)
        assert "unhappy" in response
        assert "sorry" in response.lower()

    def test_neutral_response(self):
        tracker = UGCTracker()
        entry = _make_entry(username="neutral_user", sentiment="neutral")
        response = tracker.generate_response(entry)
        assert "neutral_user" in response


class TestStats:
    def test_empty_stats(self):
        tracker = UGCTracker()
        stats = tracker.stats([])
        assert stats["total"] == 0

    def test_full_stats(self):
        tracker = UGCTracker()
        entries = [
            _make_entry(username="a", sentiment="positive"),
            _make_entry(username="a", sentiment="positive"),
            _make_entry(username="b", sentiment="negative"),
            _make_entry(username="c", sentiment="neutral", responded=True),
        ]
        stats = tracker.stats(entries)
        assert stats["total"] == 4
        assert stats["positive"] == 2
        assert stats["negative"] == 1
        assert stats["neutral"] == 1
        assert stats["unresponded"] == 3
        assert stats["top_advocates"][0] == ("a", 2)


class TestUGCEntry:
    def test_auto_id_generation(self):
        entry = UGCEntry(username="test_user")
        assert entry.entry_id  # non-empty
        assert "test_user" in entry.entry_id

    def test_auto_timestamp(self):
        entry = UGCEntry(username="test")
        assert entry.timestamp  # non-empty ISO timestamp