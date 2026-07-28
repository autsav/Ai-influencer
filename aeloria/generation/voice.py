"""Voice cloning for Aeloria reels — consistent voice across all video content.

Uses fal.ai's voice cloning / TTS endpoints to generate a consistent voice
for Aeloria. The cloned voice is used for talking-head reels, story
narrations, and voiceovers.

Usage:
    from aeloria.generation.voice import VoiceClone, generate_voiceover
    clone = VoiceClone(settings, reference_audio_url="https://r2.dev/aeloria_voice.wav")
    audio_bytes = clone.synthesize("This AI tool saves me 6 hours every week")
"""
import logging
import httpx

log = logging.getLogger(__name__)

# fal.ai TTS / voice cloning endpoints
TTS_MODEL = "fal-ai/elevenlabs/tts"
TTS_COST = 0.10  # per ~30 seconds of audio

VOICE_CLONE_MODEL = "fal-ai/elevenlabs/voice-clone"
VOICE_CLONE_COST = 0.50  # one-time cost to clone a voice


class VoiceError(Exception):
    pass


class VoiceClone:
    """Manage Aeloria's cloned voice for consistent TTS across reels.

    Workflow:
    1. Clone: Upload a reference audio clip → get a voice_id
    2. Synthesize: Use voice_id to generate speech from text
    3. Lip-sync: Combine with video via lipsync.py
    """

    def __init__(self, settings, reference_audio_url: str = "", voice_id: str = ""):
        self.settings = settings
        self.reference_audio_url = reference_audio_url
        self.voice_id = voice_id
        self._cloned = bool(voice_id)

    def clone_voice(self, reference_audio_url: str | None = None) -> str:
        """Clone a voice from a reference audio clip.

        Args:
            reference_audio_url: URL to a 30-60 second audio clip of the
                                target voice speaking clearly.

        Returns:
            voice_id: The cloned voice ID for use in synthesis

        Raises:
            VoiceError: If cloning fails
        """
        import os
        import fal_client

        url = reference_audio_url or self.reference_audio_url
        if not url:
            raise VoiceError("No reference audio URL provided for voice cloning")

        os.environ["FAL_KEY"] = self.settings.fal_key

        log.info("Cloning voice from %s", url)

        try:
            result = fal_client.subscribe(VOICE_CLONE_MODEL, arguments={
                "audio_url": url,
                "name": "Aeloria",
            })
            voice_id = result.get("voice_id", "")
            if not voice_id:
                raise VoiceError(f"Voice clone returned no voice_id: {result}")

            self.voice_id = voice_id
            self._cloned = True
            log.info("Voice cloned: id=%s, cost=$%.2f", voice_id, VOICE_CLONE_COST)
            return voice_id

        except Exception as e:
            log.error("Voice cloning failed: %s", e)
            raise VoiceError(f"Voice cloning failed: {e}") from e

    def synthesize(self, text: str, stability: float = 0.5,
                   clarity: float = 0.75) -> bytes:
        """Generate speech from text using the cloned voice.

        Args:
            text: Text to synthesize (max ~500 chars for optimal quality)
            stability: Voice stability 0-1 (higher = more consistent)
            clarity: Voice clarity 0-1 (higher = clearer enunciation)

        Returns:
            Audio bytes (MP3 or WAV)

        Raises:
            VoiceError: If synthesis fails or no voice is cloned
        """
        if not self._cloned or not self.voice_id:
            raise VoiceError("No voice cloned — call clone_voice() first")

        import os
        import fal_client

        os.environ["FAL_KEY"] = self.settings.fal_key

        log.info("Synthesizing %d chars with voice %s", len(text), self.voice_id)

        try:
            result = fal_client.subscribe(TTS_MODEL, arguments={
                "text": text[:500],  # truncate to safe limit
                "voice_id": self.voice_id,
                "stability": stability,
                "clarity": clarity,
            })

            audio_url = result.get("audio", {}).get("url")
            if not audio_url:
                audio_url = result.get("url", "")

            if not audio_url:
                raise VoiceError(f"TTS returned no audio: {result}")

            resp = httpx.get(audio_url, timeout=60)
            resp.raise_for_status()

            log.info("Voice synthesis complete: %d bytes, cost=$%.2f",
                     len(resp.content), TTS_COST)
            return resp.content

        except Exception as e:
            log.error("Voice synthesis failed: %s", e)
            raise VoiceError(f"Voice synthesis failed: {e}") from e


def generate_voiceover(
    text: str,
    settings,
    voice_id: str = "",
    reference_audio_url: str = "",
) -> bytes:
    """Convenience function: generate a voiceover clip from text.

    If voice_id is provided, uses the pre-cloned voice.
    If reference_audio_url is provided but no voice_id, clones first.
    """
    clone = VoiceClone(settings, reference_audio_url=reference_audio_url, voice_id=voice_id)

    if not clone._cloned and reference_audio_url:
        clone.clone_voice()

    return clone.synthesize(text)