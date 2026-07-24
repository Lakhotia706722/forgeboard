"""
Pydantic schemas for voice agent endpoints.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.voice_agent import CallStatus, VoiceMode


# ---------------------------------------------------------------------------
# Voice agent CRUD
# ---------------------------------------------------------------------------

class VoiceAgentCreate(BaseModel):
    """
    Attach voice capabilities to an existing agent.
    The agent_id must already exist in the workspace.
    """
    agent_id: uuid.UUID
    phone_number: str | None = Field(
        default=None,
        description="E.164 phone number, e.g. +15551234567. Leave blank to use workspace default.",
    )
    voice_mode: VoiceMode = VoiceMode.INBOUND
    tts_voice_id: str | None = None
    stt_language: str = "en-US"
    max_concurrent_calls: int = Field(default=1, ge=1, le=10)


class VoiceAgentUpdate(BaseModel):
    phone_number: str | None = None
    voice_mode: VoiceMode | None = None
    tts_voice_id: str | None = None
    stt_language: str | None = None
    max_concurrent_calls: int | None = Field(default=None, ge=1, le=10)


class VoiceAgentOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    workspace_id: uuid.UUID
    phone_number: str | None
    voice_mode: VoiceMode
    tts_voice_id: str | None
    stt_language: str
    max_concurrent_calls: int
    total_calls: int
    total_call_seconds: int
    total_escalations: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Call log
# ---------------------------------------------------------------------------

class TranscriptEntry(BaseModel):
    speaker: str
    text: str
    timestamp_ms: int = 0


class CallLogOut(BaseModel):
    id: uuid.UUID
    voice_agent_id: uuid.UUID
    workspace_id: uuid.UUID
    run_id: uuid.UUID | None
    call_sid: str
    from_number: str
    to_number: str
    direction: str
    status: CallStatus
    duration_seconds: int
    transcript: list[TranscriptEntry] = []
    consent_verified: bool
    dnc_checked: bool
    ai_disclosed: bool
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Outbound call trigger
# ---------------------------------------------------------------------------

class PlaceCallRequest(BaseModel):
    to: str = Field(description="E.164 number to call, e.g. +15551234567")
    override_message: str | None = Field(
        default=None,
        description="Optional opening message override. Defaults to agent's goal summary.",
    )
