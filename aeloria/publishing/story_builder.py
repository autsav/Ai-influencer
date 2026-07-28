"""Interactive Story builder — IG Story-specific features.

Generates interactive Story content with polls, quizzes, countdown timers,
question stickers, and music overlays via the Instagram Graph API.

Usage:
    from aeloria.publishing.story_builder import StoryBuilder, StoryContent
    builder = StoryBuilder(settings)
    story = builder.create_poll_story("Which AI tool do you use?", ["ChatGPT", "Claude"])
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


@dataclass
class StoryContent:
    """Interactive Instagram Story content."""
    type: str = "static"  # "static", "poll", "quiz", "countdown", "question", "slider"
    image_url: str = ""
    background_color: str = "#000000"
    caption: str = ""
    # Poll-specific
    poll_question: str = ""
    poll_options: list[str] = field(default_factory=list)
    # Quiz-specific
    quiz_question: str = ""
    quiz_options: list[str] = field(default_factory=list)
    quiz_correct_answer: int = 0
    # Countdown-specific
    countdown_text: str = ""
    countdown_end_time: str = ""  # ISO timestamp
    # Question sticker
    question_text: str = ""
    question_box_style: str = "default"
    # Slider
    slider_emoji: str = "🔥"
    slider_question: str = ""
    # Music
    music_track_id: str = ""
    music_start_time_ms: int = 0
    # Metadata
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class StoryBuilder:
    """Build interactive Instagram Story content.

    Creates StoryContent objects that can be published via the Meta Graph API.
    Each story type supports different interactive stickers.
    """

    def __init__(self, settings=None):
        self.settings = settings

    def create_static_story(self, image_url: str, caption: str = "") -> StoryContent:
        """Create a simple static image story."""
        return StoryContent(
            type="static",
            image_url=image_url,
            caption=caption,
        )

    def create_poll_story(self, image_url: str, question: str,
                          options: list[str]) -> StoryContent:
        """Create a poll story with two options."""
        if len(options) != 2:
            raise ValueError("Instagram polls require exactly 2 options")
        return StoryContent(
            type="poll",
            image_url=image_url,
            poll_question=question,
            poll_options=options,
        )

    def create_quiz_story(self, image_url: str, question: str,
                          options: list[str], correct_answer: int = 0) -> StoryContent:
        """Create a quiz story with 2-4 options and a correct answer."""
        if len(options) < 2 or len(options) > 4:
            raise ValueError("Quiz stories require 2-4 options")
        if correct_answer < 0 or correct_answer >= len(options):
            raise ValueError("correct_answer index out of range")
        return StoryContent(
            type="quiz",
            image_url=image_url,
            quiz_question=question,
            quiz_options=options,
            quiz_correct_answer=correct_answer,
        )

    def create_countdown_story(self, image_url: str, text: str,
                               hours_from_now: float = 24.0) -> StoryContent:
        """Create a countdown timer story."""
        end_time = (datetime.now(timezone.utc) + timedelta(hours=hours_from_now)).isoformat()
        return StoryContent(
            type="countdown",
            image_url=image_url,
            countdown_text=text,
            countdown_end_time=end_time,
        )

    def create_question_story(self, image_url: str, question: str,
                              box_style: str = "default") -> StoryContent:
        """Create a question sticker story for audience engagement."""
        valid_styles = {"default", "heart", "light", "dark"}
        if box_style not in valid_styles:
            box_style = "default"
        return StoryContent(
            type="question",
            image_url=image_url,
            question_text=question,
            question_box_style=box_style,
        )

    def create_slider_story(self, image_url: str, question: str,
                            emoji: str = "🔥") -> StoryContent:
        """Create an emoji slider story."""
        return StoryContent(
            type="slider",
            image_url=image_url,
            slider_question=question,
            slider_emoji=emoji,
        )

    def add_music(self, story: StoryContent, track_id: str,
                  start_ms: int = 0) -> StoryContent:
        """Add a music track to any story type."""
        story.music_track_id = track_id
        story.music_start_time_ms = start_ms
        return story

    def to_graph_api_payload(self, story: StoryContent) -> dict:
        """Convert StoryContent to Instagram Graph API payload.

        Returns the interactive elements config for the Story API.
        """
        payload = {
            "media_type": "STORY",
            "image_url": story.image_url,
            "caption": story.caption,
        }

        if story.type == "poll":
            payload["interactive_stickers"] = [{
                "type": "poll",
                "question": story.poll_question,
                "options": story.poll_options,
            }]
        elif story.type == "quiz":
            payload["interactive_stickers"] = [{
                "type": "quiz",
                "question": story.quiz_question,
                "options": story.quiz_options,
                "correct_answer": story.quiz_correct_answer,
            }]
        elif story.type == "countdown":
            payload["interactive_stickers"] = [{
                "type": "countdown",
                "text": story.countdown_text,
                "end_time": story.countdown_end_time,
            }]
        elif story.type == "question":
            payload["interactive_stickers"] = [{
                "type": "question",
                "text": story.question_text,
                "box_style": story.question_box_style,
            }]
        elif story.type == "slider":
            payload["interactive_stickers"] = [{
                "type": "slider",
                "question": story.slider_question,
                "emoji": story.slider_emoji,
            }]

        if story.music_track_id:
            payload["music_track_id"] = story.music_track_id
            payload["music_start_time_ms"] = story.music_start_time_ms

        return payload