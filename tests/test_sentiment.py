"""Tests for audience sentiment analysis."""
import pytest
from aeloria.analytics.sentiment import (
    analyze_comments,
    _classify_sentiment,
    _extract_question,
    _extract_content_request,
    SentimentResult,
)


class TestClassifySentiment:
    def test_positive(self):
        s, pos, neg = _classify_sentiment("This is amazing! Love it 🔥")
        assert s == "positive"
        assert "amazing" in pos
        assert "love" in pos

    def test_negative(self):
        s, pos, neg = _classify_sentiment("This is terrible and useless")
        assert s == "negative"
        assert "terrible" in neg
        assert "useless" in neg

    def test_neutral(self):
        s, pos, neg = _classify_sentiment("Just a regular comment about the post")
        assert s == "neutral"

    def test_emoji_positive(self):
        s, pos, neg = _classify_sentiment("❤️❤️❤️")
        assert s == "positive"

    def test_mixed_neutral(self):
        s, pos, neg = _classify_sentiment("love it but also hate it")
        assert s == "neutral"  # equal positive and negative

    def test_empty(self):
        s, pos, neg = _classify_sentiment("")
        assert s == "neutral"


class TestExtractQuestion:
    def test_question_detected(self):
        q = _extract_question("How do you automate your emails?")
        assert q is not None
        assert "How" in q

    def test_not_a_question(self):
        q = _extract_question("Great post about AI tools")
        assert q is None

    def test_what_question(self):
        q = _extract_question("What AI tool is this?")
        assert q is not None

    def test_truncated(self):
        long_q = "How " + "x" * 300
        q = _extract_question(long_q)
        assert q is not None
        assert len(q) <= 200


class TestExtractContentRequest:
    def test_make_a_request(self):
        r = _extract_content_request("Can you make a video on AI automation?")
        assert r is not None

    def test_want_to_see(self):
        r = _extract_content_request("Would love to see a tutorial on this!")
        assert r is not None

    def test_no_request(self):
        r = _extract_content_request("Great post!")
        assert r is None


class TestAnalyzeComments:
    def test_empty_list(self):
        result = analyze_comments([])
        assert result.total_comments == 0
        assert result.sentiment_score == 0.0

    def test_mixed_sentiments(self):
        comments = [
            "This is amazing! 🔥",
            "Love this workflow, so helpful",
            "This is terrible and useless",
            "Just a normal comment",
            "Great content as always ❤️",
        ]
        result = analyze_comments(comments)
        assert result.total_comments == 5
        assert result.positive_count == 3
        assert result.negative_count == 1
        assert result.neutral_count == 1
        assert result.sentiment_score > 0  # net positive

    def test_all_negative(self):
        comments = ["terrible", "awful", "hate this", "useless"]
        result = analyze_comments(comments)
        assert result.negative_count == 4
        assert result.sentiment_score < 0

    def test_questions_extracted(self):
        comments = [
            "How do you do this?",
            "What tool is that?",
            "Great post!",
        ]
        result = analyze_comments(comments)
        assert len(result.top_questions) == 2

    def test_content_requests_extracted(self):
        comments = [
            "Make a video on email automation please",
            "Would love to see a tutorial on this",
            "Nice photo!",
        ]
        result = analyze_comments(comments)
        assert len(result.content_requests) == 2

    def test_top_words(self):
        comments = [
            "amazing amazing amazing",
            "love it love",
            "terrible",
        ]
        result = analyze_comments(comments)
        assert result.top_positive_words[0][0] == "amazing"
        assert result.top_positive_words[0][1] == 1  # set-based dedup per comment

    def test_rates_calculated(self):
        comments = ["love it", "hate it", "ok"]
        result = analyze_comments(comments)
        assert result.positive_rate == pytest.approx(1/3)
        assert result.negative_rate == pytest.approx(1/3)

    def test_empty_comments_skipped(self):
        result = analyze_comments(["", "  ", "love it"])
        assert result.total_comments == 3  # counted but empty skipped in analysis
        assert result.positive_count == 1