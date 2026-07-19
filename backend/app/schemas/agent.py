"""
Pydantic schemas for agent endpoints.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.agent import AgentStatus, TriggerType


# ---------------------------------------------------------------------------
# Connector summary embedded in agent responses
# ---------------------------------------------------------------------------

class ConnectorSummary(BaseModel):
    id: uuid.UUID
    name: str
    connector_type: str
    status: str

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    goal: str = Field(
        min_length=10,
        max_length=4000,
        description="Plain-language description of what this agent should do.",
    )
    connector_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="IDs of connectors this agent can use. Must belong to the same workspace.",
    )
    trigger_type: TriggerType = TriggerType.MANUAL
    cron_schedule: str | None = Field(
        default=None,
        description='Cron expression for scheduled triggers, e.g. "0 9 * * 1-5"',
    )
    requires_approval: bool = False


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    goal: str | None = Field(default=None, min_length=10, max_length=4000)
    connector_ids: list[uuid.UUID] | None = None
    trigger_type: TriggerType | None = None
    cron_schedule: str | None = None
    requires_approval: bool | None = None


class AgentStatusUpdate(BaseModel):
    status: AgentStatus


# ---------------------------------------------------------------------------
# Response bodies
# ---------------------------------------------------------------------------

class AgentOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    goal: str
    status: AgentStatus
    trigger_type: TriggerType
    cron_schedule: str | None
    requires_approval: bool
    total_runs: int
    total_cost_usd_cents: int
    consecutive_failures: int
    connectors: list[ConnectorSummary] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Agent config — compiled object passed to the orchestration engine (Phase 4)
# ---------------------------------------------------------------------------

class ToolDefinition(BaseModel):
    """A single tool the agent can call, in a format compatible with the Anthropic API."""
    name: str
    description: str
    input_schema: dict[str, Any]


class AgentConfig(BaseModel):
    """
    The compiled runtime configuration for an agent run.
    Stored as JSON in agents.agent_config_json and consumed by Phase 4 Celery tasks.
    """
    agent_id: str
    workspace_id: str
    system_prompt: str
    tools: list[ToolDefinition]
    # Connector metadata needed at runtime to actually execute tool calls
    connector_map: dict[str, dict[str, Any]]  # connector_id -> {type, config, ...}
