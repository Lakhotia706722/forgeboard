"""
Provider factories — return the configured concrete implementation.
Swapping vendors = change STT_PROVIDER / TTS_PROVIDER in .env.
"""
from functools import lru_cache

from app.core.config import settings
from app.voice.interfaces import STTProvider, TTSProvider, TelephonyProvider


@lru_cache(maxsize=1)
def get_telephony_provider() -> TelephonyProvider:
    # Currently only Twilio is wired. Extend the if/elif chain for Telnyx, etc.
    from app.voice.providers.twilio_provider import TwilioProvider
    return TwilioProvider()


def get_stt_provider() -> STTProvider:
    """Returns a NEW STT instance per call (stateful WebSocket per session)."""
    provider = settings.STT_PROVIDER.lower()
    if provider == "deepgram":
        from app.voice.providers.deepgram_stt import DeepgramSTT
        return DeepgramSTT()
    raise ValueError(f"Unknown STT_PROVIDER: {provider!r}")


@lru_cache(maxsize=1)
def get_tts_provider() -> TTSProvider:
    provider = settings.TTS_PROVIDER.lower()
    if provider == "elevenlabs":
        from app.voice.providers.elevenlabs_tts import ElevenLabsTTS
        return ElevenLabsTTS()
    raise ValueError(f"Unknown TTS_PROVIDER: {provider!r}")
