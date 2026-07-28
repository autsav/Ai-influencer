"""Tests for voice cloning and TTS."""
import pytest
from unittest.mock import MagicMock, patch
from aeloria.generation.voice import VoiceClone, VoiceError, generate_voiceover, TTS_COST


@patch("httpx.get")
@patch("fal_client.subscribe")
def test_synthesize_success(mock_subscribe, mock_httpx_get):
    mock_subscribe.return_value = {"audio": {"url": "https://example.com/audio.mp3"}}
    mock_httpx_get.return_value = MagicMock(content=b"fake-audio", raise_for_status=lambda: None)

    settings = MagicMock()
    settings.fal_key = "fake-key"

    clone = VoiceClone(settings, voice_id="voice-123")
    audio = clone.synthesize("Hello world")
    assert audio == b"fake-audio"


def test_synthesize_no_voice_raises():
    settings = MagicMock()
    settings.fal_key = "fake-key"
    clone = VoiceClone(settings)  # no voice_id
    with pytest.raises(VoiceError, match="No voice cloned"):
        clone.synthesize("Hello")


@patch("fal_client.subscribe")
def test_clone_voice_success(mock_subscribe):
    mock_subscribe.return_value = {"voice_id": "new-voice-456"}
    settings = MagicMock()
    settings.fal_key = "fake-key"

    clone = VoiceClone(settings, reference_audio_url="https://example.com/ref.wav")
    voice_id = clone.clone_voice()
    assert voice_id == "new-voice-456"
    assert clone._cloned is True


def test_clone_voice_no_url_raises():
    settings = MagicMock()
    settings.fal_key = "fake-key"
    clone = VoiceClone(settings)
    with pytest.raises(VoiceError, match="No reference audio"):
        clone.clone_voice()


@patch("fal_client.subscribe")
def test_clone_voice_failure_raises(mock_subscribe):
    mock_subscribe.side_effect = Exception("API error")
    settings = MagicMock()
    settings.fal_key = "fake-key"
    clone = VoiceClone(settings, reference_audio_url="https://example.com/ref.wav")
    with pytest.raises(VoiceError, match="Voice cloning failed"):
        clone.clone_voice()


@patch("httpx.get")
@patch("fal_client.subscribe")
def test_synthesize_truncates_long_text(mock_subscribe, mock_httpx_get):
    mock_subscribe.return_value = {"audio": {"url": "https://example.com/a.mp3"}}
    mock_httpx_get.return_value = MagicMock(content=b"audio", raise_for_status=lambda: None)

    settings = MagicMock()
    settings.fal_key = "fake-key"
    clone = VoiceClone(settings, voice_id="v-1")

    long_text = "A" * 600
    clone.synthesize(long_text)

    call_args = mock_subscribe.call_args
    sent_text = call_args.kwargs["arguments"]["text"]
    assert len(sent_text) == 500  # truncated


@patch("httpx.get")
@patch("fal_client.subscribe")
def test_generate_voiceover_with_existing_voice(mock_subscribe, mock_httpx_get):
    mock_subscribe.return_value = {"audio": {"url": "https://example.com/a.mp3"}}
    mock_httpx_get.return_value = MagicMock(content=b"audio", raise_for_status=lambda: None)

    settings = MagicMock()
    settings.fal_key = "fake-key"
    audio = generate_voiceover("Hello", settings, voice_id="existing-voice")
    assert audio == b"audio"