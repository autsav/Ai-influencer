"""Audience sentiment analysis for Instagram comments.

Analyzes IG comments for sentiment, recurring questions, and content requests.
Feeds into optimizer + content calendar to inform what the audience wants.

Usage:
    from aeloria.analytics.sentiment import analyze_comments, SentimentResult
    result = analyze_comments(comments, settings)
    print(f"Positive: {result.positive_count}, Negative: {result.negative_count}")
    print(f"Top questions: {result.top_questions}")
"""
import logging
import re
from dataclasses import dataclass, field
from collections import Counter

log = logging.getLogger(__name__)

# Simple lexicon-based sentiment (no external API needed)
# Positive and negative word lists — can be extended or replaced with LLM
_POSITIVE_WORDS = {
    "love", "amazing", "awesome", "great", "perfect", "incredible", "fantastic",
    "brilliant", "helpful", "useful", "saved", "game-changer", "gamechanger",
    "wow", "cool", "nice", "thanks", "thank", "appreciate", "inspiring",
    "motivated", "learned", "useful", "insightful", "clever", "smart",
    "best", "favorite", "favourite", "follow", "following", "🔥", "❤️", "👍",
    "👏", "💯", "✨", "great", "good", "impressed", "recommend",
}

_NEGATIVE_WORDS = {
    "bad", "terrible", "awful", "hate", "stupid", "useless", "waste", "boring",
    "disappointed", "disappointing", "confusing", "confused", "broken", "fail",
    "failed", "wrong", "scam", "fake", "misleading", "overpriced", "slow",
    "cringy", "cringe", "👎", "😡", "🤮", "worse", "worst",
}

_QUESTION_PATTERN = re.compile(
    r'^(how|what|why|when|where|which|who|can you|do you|could you|would you|'
    r'is there|are there|will you|have you|did you)\b',
    re.IGNORECASE,
)

# Content request signals
_REQUEST_PATTERNS = [
    re.compile(r'(make a|do a|post about|video on|reel on|talk about)\b(.+)', re.IGNORECASE),
    re.compile(r'(would love to see|want to see|wish you.?d)\b(.+)', re.IGNORECASE),
    re.compile(r'(tutorial|guide|walkthrough|step.by.step)\b(.*)', re.IGNORECASE),
]


@dataclass
class SentimentResult:
    """Aggregated sentiment analysis of comments."""
    total_comments: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    positive_rate: float = 0.0
    negative_rate: float = 0.0
    top_positive_words: list[tuple[str, int]] = field(default_factory=list)
    top_negative_words: list[tuple[str, int]] = field(default_factory=list)
    top_questions: list[str] = field(default_factory=list)
    content_requests: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0  # -1.0 to +1.0

    def __repr__(self):
        return (
            f"SentimentResult(total={self.total_comments}, "
            f"+{self.positive_count}/-{self.negative_count}/={self.neutral_count}, "
            f"score={self.sentiment_score:+.2f}, "
            f"questions={len(self.top_questions)}, "
            f"requests={len(self.content_requests)})"
        )


def _classify_sentiment(text: str) -> tuple[str, list[str], list[str]]:
    """Classify a single comment as positive/negative/neutral.

    Returns (sentiment, matched_positive_words, matched_negative_words).
    """
    text_lower = text.lower()
    words = set(re.findall(r'\b\w+\b|🔥|❤️|👍|👏|💯|✨|👎|😡', text_lower))

    pos_matches = words & _POSITIVE_WORDS
    neg_matches = words & _NEGATIVE_WORDS

    if len(pos_matches) > len(neg_matches):
        return "positive", list(pos_matches), list(neg_matches)
    elif len(neg_matches) > len(pos_matches):
        return "negative", list(pos_matches), list(neg_matches)
    else:
        if pos_matches and neg_matches:
            return "neutral", list(pos_matches), list(neg_matches)
        return "neutral", list(pos_matches), list(neg_matches)


def _extract_question(text: str) -> str | None:
    """Extract a question from a comment, if present."""
    if _QUESTION_PATTERN.match(text.strip()):
        # Truncate to first 200 chars for storage
        return text.strip()[:200]
    return None


def _extract_content_request(text: str) -> str | None:
    """Extract a content request from a comment."""
    for pattern in _REQUEST_PATTERNS:
        match = pattern.search(text)
        if match:
            # Return the full request, truncated
            request = text.strip()[:200]
            return request
    return None


def analyze_comments(comments: list[str], settings=None) -> SentimentResult:
    """Analyze a list of comment texts for sentiment and content signals.

    Args:
        comments: List of comment text strings
        settings: App settings (unused for lexicon-based, reserved for LLM mode)

    Returns:
        SentimentResult with aggregated sentiment data
    """
    result = SentimentResult(total_comments=len(comments))

    pos_word_counter = Counter()
    neg_word_counter = Counter()

    for text in comments:
        if not text or not text.strip():
            continue

        # Classify sentiment
        sentiment, pos_words, neg_words = _classify_sentiment(text)

        if sentiment == "positive":
            result.positive_count += 1
            pos_word_counter.update(pos_words)
        elif sentiment == "negative":
            result.negative_count += 1
            neg_word_counter.update(neg_words)
        else:
            result.neutral_count += 1

        # Extract questions
        question = _extract_question(text)
        if question:
            result.top_questions.append(question)

        # Extract content requests
        request = _extract_content_request(text)
        if request:
            result.content_requests.append(request)

    # Calculate rates
    if result.total_comments > 0:
        result.positive_rate = result.positive_count / result.total_comments
        result.negative_rate = result.negative_count / result.total_comments

        # Sentiment score: -1.0 to +1.0
        result.sentiment_score = (
            (result.positive_count - result.negative_count) / result.total_comments
        )

    # Top words
    result.top_positive_words = pos_word_counter.most_common(10)
    result.top_negative_words = neg_word_counter.most_common(10)

    # Limit questions and requests to top 20
    result.top_questions = result.top_questions[:20]
    result.content_requests = result.content_requests[:20]

    log.info(
        "Sentiment analysis: %d comments, +%d/-%d/=%d, score=%+.2f, %d questions, %d requests",
        result.total_comments, result.positive_count, result.negative_count,
        result.neutral_count, result.sentiment_score,
        len(result.top_questions), len(result.content_requests),
    )

    return result