"""Voice cloning for Aeloria reels — consistent voice across all video content.

Uses fal.ai's ElevenLabs endpoint to generate a consistent voice for Aeloria.
The cloned voice is used for talking-head reels, story narrations, and voiceovers.

Sage-Mystic pivot 2026-08-14:
    Primary route: FAL → ElevenLabs multilingual-v2 (LIVE 2026-08-14).
    The bare `fal-ai/elevenlabs/tts` endpoint retired 2026-08; do not use.
    Speed:  0.85 (sage-mystic slow cadence)
    Voice:  EXAVITQu4vr4xnSDxMaL (Bella — ElevenLabs built-in)

Usage:
    from aeloria.generation.voice import generate_voiceover
    audio_bytes = generate_voiceover(
        "I want to show you what I found.",
        settings,
        # reference_audio_url=""  # leave blank to use the default Bella voice
    )
"""
import logging
import httpx

log = logging.getLogger(__name__)

# fal.ai ElevenLabs — LIVE endpoint (the bare /tts was retired 2026-08)
TTS_MODEL = "fal-ai/elevenlabs/tts/multilingual-v2"
TTS_COST = 0.10  # per ~30 seconds of audio (FAL-billed on completion)

# Legacy voice-clone model — kept for users who DO want a custom voice clone.
# Active only if a reference_audio_url is passed in.
VOICE_CLONE_MODEL = "fal-ai/elevenlabs/voice-clone"
VOICE_CLONE_COST = 0.50  # one-time cost to clone a voice

# Sage-Mystic defaults (2026-08-14 pivot)
DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  # Bella — warm, conversational
DEFAULT_SPEED = 0.85
DEFAULT_STABILITY = 0.55
DEFAULT_CLARITY = 0.78


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

    def clone_voice(self, reference_audio_url=None) -> str:
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

    def synthesize(self, text: str, stability=None,
                   clarity=None, speed=None) -> bytes:
        """Generate speech from text using the cloned/default voice.

        Args:
            text: Text to synthesize. ElevenLabs multilingual-v2 supports up to
                  5000 chars; the script_agent batches long scripts into chunks.
            stability: Voice stability 0-1 (higher = more consistent).
                       Default: 0.55 (sage-mystic warm-but-grounded balance).
            clarity: Voice clarity / similarity_boost 0-1 (higher = clearer
                     enunciation, more "this voice").
                     Default: 0.78 (gentle similarity lift).
            speed: Playback speed multiplier. ElevenLabs accepts 0.70..1.20.
                   Default: 0.85 (sage-mystic slow cadence; trust the silence).

        Returns:
            Audio bytes (MP3).

        Raises:
            VoiceError: If synthesis fails or no voice is cloned/selected.
        """
        if not self._cloned or not self.voice_id:
            raise VoiceError("No voice cloned — call clone_voice() first or pass voice_id to __init__()")

        import os
        import json
        import urllib.request
        import fal_client

        os.environ["FAL_KEY"] = self.settings.fal_key

        eff_stability = stability if stability is not None else DEFAULT_STABILITY
        eff_clarity = clarity if clarity is not None else DEFAULT_CLARITY
        eff_speed = speed if speed is not None else DEFAULT_SPEED

        log.info("Synthesizing %d chars with voice %s (stability=%.2f, clarity=%.2f, speed=%.2f)",
                 len(text), self.voice_id, eff_stability, eff_clarity, eff_speed)

        try:
            result = fal_client.subscribe(
                TTS_MODEL,
                arguments={
                    "text": text,
                    "voice_id": self.voice_id,
                    "stability": eff_stability,
                    "similarity_boost": eff_clarity,
                    "voice_settings": {"speed": eff_speed},
                },
                with_logs=False,
            )

            audio_url = None
            if isinstance(result, dict):
                a = result.get("audio")
                if isinstance(a, dict):
                    audio_url = a.get("url") or a.get("audio_url")
                elif isinstance(a, str):
                    audio_url = a
                audio_url = audio_url or result.get("audio_url") or result.get("url")

            if not audio_url:
                raise VoiceError(f"TTS returned no audio: {json.dumps(result)[:500]}")

            audio_bytes = urllib.request.urlopen(audio_url, timeout=60).read()
            if not audio_bytes or audio_bytes[:3] not in (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
                raise VoiceError(f"TTS audio download invalid (header={audio_bytes[:8]!r})")

            log.info("Voice synthesis complete: %d bytes, cost=$%.2f",
                     len(audio_bytes), TTS_COST)
            return audio_bytes

        except VoiceError:
            raise
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