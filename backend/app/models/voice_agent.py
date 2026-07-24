"""
VoiceAgent — extends the base Agent with telephony-specific fields.

Uses joined-table inheritance so voice agents appear on the Kanban board
alongside regular agents and share the same run/audit machinery from Phases 4–6.

voice_agents.agent_id FK → agents.id  (one-to-one extension row)
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VoiceMode(str, PyEnum):
    INBOUND = "inbound"    # agent answers calls to its number
    OUTBOUND = "outbound"  # agent places calls to a list / on demand


class CallStatus(str, PyEnum):
    IDLE = "idle"
    RINGING = "ringing"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TRANSFERRED = "transferred"


class VoiceAgent(Base):
    __tablename__ = "voice_agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # One-to-one with agents table
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Telephony config
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    voice_mode: Mapped[VoiceMode] = mapped_column(
        SAEnum(VoiceMode, name="voicemode"),
        default=VoiceMode.INBOUND,
        nullable=False,
    )
    # Twilio-specific: SID of the purchased/configured phone number
    phone_number_sid: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Voice / STT / TTS config (overrides global settings for this agent)
    tts_voice_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stt_language: Mapped[str] = mapped_column(String(10), default="en-US", nullable=False)

    # Concurrent call cap for this specific agent (workspace cap enforced separately)
    max_concurrent_calls: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Counters updated by the call engine
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_call_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_escalations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationship back to base Agent
    agent: Mapped["Agent"] = relationship("Agent")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<VoiceAgent agent_id={self.agent_id} mode={self.voice_mode} phone={self.phone_number}>"


class CallLog(Base):
    """
    One record per phone call. Linked to an AgentRun for the full trace.
    Populated by the call engine in real time.
    """
    __tablename__ = "call_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    voice_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("voice_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Linked run record (created when call starts)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Telephony identifiers
    call_sid: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    from_number: Mapped[str] = mapped_column(String(30), nullable=False)
    to_number: Mapped[str] = mapped_column(String(30), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # inbound|outbound

    status: Mapped[CallStatus] = mapped_column(
        SAEnum(CallStatus, name="callstatus"),
        default=CallStatus.IDLE,
        nullable=False,
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Transcript stored as JSON array of {speaker, text, timestamp_ms}
    transcript_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Compliance flags (populated by Phase 8b)
    consent_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dnc_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_disclosed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<CallLog id={self.id} sid={self.call_sid} status={self.status}>"
