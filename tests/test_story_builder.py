"""Tests for interactive Story builder."""
import pytest
from aeloria.publishing.story_builder import StoryBuilder, StoryContent


class TestCreateStaticStory:
    def test_basic(self):
        builder = StoryBuilder()
        story = builder.create_static_story("https://img.jpg", "Test caption")
        assert story.type == "static"
        assert story.image_url == "https://img.jpg"
        assert story.caption == "Test caption"


class TestCreatePollStory:
    def test_basic(self):
        builder = StoryBuilder()
        story = builder.create_poll_story("https://img.jpg", "Which AI tool?", ["ChatGPT", "Claude"])
        assert story.type == "poll"
        assert story.poll_question == "Which AI tool?"
        assert story.poll_options == ["ChatGPT", "Claude"]

    def test_requires_two_options(self):
        builder = StoryBuilder()
        with pytest.raises(ValueError, match="exactly 2"):
            builder.create_poll_story("https://img.jpg", "Q", ["A"])
        with pytest.raises(ValueError, match="exactly 2"):
            builder.create_poll_story("https://img.jpg", "Q", ["A", "B", "C"])


class TestCreateQuizStory:
    def test_basic(self):
        builder = StoryBuilder()
        story = builder.create_quiz_story("https://img.jpg", "What is AI?",
                                           ["Robot", "Software", "Both"], correct_answer=2)
        assert story.type == "quiz"
        assert story.quiz_correct_answer == 2

    def test_too_few_options(self):
        builder = StoryBuilder()
        with pytest.raises(ValueError, match="2-4"):
            builder.create_quiz_story("https://img.jpg", "Q", ["A"])

    def test_too_many_options(self):
        builder = StoryBuilder()
        with pytest.raises(ValueError, match="2-4"):
            builder.create_quiz_story("https://img.jpg", "Q", ["A", "B", "C", "D", "E"])

    def test_invalid_correct_answer(self):
        builder = StoryBuilder()
        with pytest.raises(ValueError, match="out of range"):
            builder.create_quiz_story("https://img.jpg", "Q", ["A", "B"], correct_answer=5)


class TestCreateCountdownStory:
    def test_basic(self):
        builder = StoryBuilder()
        story = builder.create_countdown_story("https://img.jpg", "Product launch!", hours_from_now=48)
        assert story.type == "countdown"
        assert story.countdown_text == "Product launch!"
        assert story.countdown_end_time  # non-empty ISO timestamp


class TestCreateQuestionStory:
    def test_basic(self):
        builder = StoryBuilder()
        story = builder.create_question_story("https://img.jpg", "Ask me anything!")
        assert story.type == "question"
        assert story.question_text == "Ask me anything!"

    def test_invalid_style_defaults(self):
        builder = StoryBuilder()
        story = builder.create_question_story("https://img.jpg", "Q", box_style="invalid")
        assert story.question_box_style == "default"


class TestCreateSliderStory:
    def test_basic(self):
        builder = StoryBuilder()
        story = builder.create_slider_story("https://img.jpg", "How hot is this tool?", emoji="🚀")
        assert story.type == "slider"
        assert story.slider_emoji == "🚀"


class TestAddMusic:
    def test_adds_music_to_story(self):
        builder = StoryBuilder()
        story = builder.create_static_story("https://img.jpg")
        builder.add_music(story, track_id="track-123", start_ms=5000)
        assert story.music_track_id == "track-123"
        assert story.music_start_time_ms == 5000


class TestToGraphApiPayload:
    def test_static_payload(self):
        builder = StoryBuilder()
        story = builder.create_static_story("https://img.jpg", "Cap")
        payload = builder.to_graph_api_payload(story)
        assert payload["media_type"] == "STORY"
        assert payload["image_url"] == "https://img.jpg"
        assert "interactive_stickers" not in payload

    def test_poll_payload(self):
        builder = StoryBuilder()
        story = builder.create_poll_story("https://img.jpg", "Q?", ["A", "B"])
        payload = builder.to_graph_api_payload(story)
        assert payload["interactive_stickers"][0]["type"] == "poll"
        assert payload["interactive_stickers"][0]["question"] == "Q?"

    def test_quiz_payload(self):
        builder = StoryBuilder()
        story = builder.create_quiz_story("https://img.jpg", "Q?", ["A", "B"], correct_answer=1)
        payload = builder.to_graph_api_payload(story)
        assert payload["interactive_stickers"][0]["type"] == "quiz"
        assert payload["interactive_stickers"][0]["correct_answer"] == 1

    def test_countdown_payload(self):
        builder = StoryBuilder()
        story = builder.create_countdown_story("https://img.jpg", "Launch!")
        payload = builder.to_graph_api_payload(story)
        assert payload["interactive_stickers"][0]["type"] == "countdown"
        assert payload["interactive_stickers"][0]["text"] == "Launch!"

    def test_question_payload(self):
        builder = StoryBuilder()
        story = builder.create_question_story("https://img.jpg", "Ask me")
        payload = builder.to_graph_api_payload(story)
        assert payload["interactive_stickers"][0]["type"] == "question"

    def test_slider_payload(self):
        builder = StoryBuilder()
        story = builder.create_slider_story("https://img.jpg", "Rate this")
        payload = builder.to_graph_api_payload(story)
        assert payload["interactive_stickers"][0]["type"] == "slider"

    def test_music_in_payload(self):
        builder = StoryBuilder()
        story = builder.create_static_story("https://img.jpg")
        builder.add_music(story, "track-123")
        payload = builder.to_graph_api_payload(story)
        assert payload["music_track_id"] == "track-123"