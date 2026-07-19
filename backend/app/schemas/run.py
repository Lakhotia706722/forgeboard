"""
Pydantic schemas for agent run endpoints.
"""
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

from app.models.run import RunStatus


# ---------------------------------------------------------------------------
# Trace events — each step of what the agent did during a run
# ---------------------------------------------------------------------------

class TraceEvent(BaseModel):
    """A single event in the agent's execution trace."""
    seq: int                          # sequence number
    type: str                         # "llm_call", "tool_call", "tool_result", "error", "output"
    timestamp: str                    # ISO 8601
    data: dict[str, Any]             # event-specific payload


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class RunOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    workspace_id: uuid.UUID
    status: RunStatus
    trigger_source: str
    celery_task_id: str | None
    output: str | None
    error: str | None
    input_tokens: int
    output_tokens: int
    cost_usd_cents: int
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunDetail(RunOut):
    """Extended run response that includes the full trace."""
    trace: list[TraceEvent] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class TriggerRunRequest(BaseModel):
    trigger_source: str = "manual"
