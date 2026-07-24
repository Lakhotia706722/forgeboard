"""
Vendor-abstraction interfaces for telephony, STT, and TTS.

Design intent:
  - Twilio is wired in Phase 8a as the only concrete implementation.
  - Swapping to Telnyx, Vonage, or another provider = implement the interface
    + change a config value. No other code changes needed.
  - Same pattern for STT (Deepgram wired; swappable to AssemblyAI, Whisper, etc.)
    and TTS (ElevenLabs wired; swappable to Azure, Google, etc.)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Shared data types
# ---------------------------------------------------------------------------

@dataclass
class CallRecord:
    """Normalised call record returned by the telephony provider."""
    call_sid: str              # provider-assigned call ID
    from_number: str
    to_number: str
    direction: str             # "inbound" | "outbound"
    status: str                # "initiated" | "ringing" | "in-progress" | "completed" | "failed"
    duration_seconds: int = 0
    raw: dict = field(default_factory=dict)  # full provider response


@dataclass
class TranscriptSegment:
    """One utterance from the real-time STT stream."""
    speaker: str               # "agent" | "human"
    text: str
    is_final: bool
    confidence: float = 1.0
    timestamp_ms: int = 0


@dataclass
class TTSAudio:
    """Audio bytes + metadata returned by a TTS provider."""
    audio_bytes: bytes
    mime_type: str = "audio/mpeg"
    duration_ms: int = 0


# ---------------------------------------------------------------------------
# Telephony interface
# ---------------------------------------------------------------------------

class TelephonyProvider(ABC):
    """Abstract interface for telephony vendors (Twilio, Telnyx, etc.)."""

    @abstractmethod
    async def place_outbound_call(
        self,
        to: str,
        from_: str,
        webhook_url: str,
        extra: dict[str, Any] | None = None,
    ) -> CallRecord:
        """Initiate an outbound call. Returns a CallRecord with the provider SID."""

    @abstractmethod
    async def hang_up(self, call_sid: str) -> None:
        """Terminate an active call."""

    @abstractmethod
    async def transfer_to_human(
        self,
        call_sid: str,
        human_number: str,
        context_twiml: str | None = None,
    ) -> None:
        """
        Warm transfer: bridge the current call to a human agent.
        context_twiml carries a brief read-out of call context before connecting.
        """

    @abstractmethod
    def generate_answer_twiml(
        self,
        websocket_stream_url: str,
        welcome_message: str | None = None,
    ) -> str:
        """
        Return TwiML (or equivalent) to answer an inbound call and start
        a bidirectional audio stream to our WebSocket endpoint.
        """


# ---------------------------------------------------------------------------
# STT interface
# ---------------------------------------------------------------------------

class STTProvider(ABC):
    """Abstract interface for speech-to-text vendors."""

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_chunk: bytes,
        sample_rate: int = 8000,
        encoding: str = "mulaw",
    ) -> list[TranscriptSegment]:
        """
        Process a raw audio chunk and return any completed transcript segments.
        Called repeatedly as audio arrives from the telephony stream.
        """

    @abstractmethod
    async def close(self) -> None:
        """Flush and clean up any open connections."""


# ---------------------------------------------------------------------------
# TTS interface
# ---------------------------------------------------------------------------

class TTSProvider(ABC):
    """Abstract interface for text-to-speech vendors."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
        speed: float = 1.0,
    ) -> TTSAudio:
        """Convert text to audio bytes. Returns TTSAudio."""
