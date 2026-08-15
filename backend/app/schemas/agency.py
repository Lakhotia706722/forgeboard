"""
Pydantic schemas for the agency endpoints — Phase 9c.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AgencyWorkspaceSummary(BaseModel):
    workspace_id: uuid.UUID
    workspace_name: str
    workspace_slug: str
    agent_count: int
    live_agent_count: int

    model_config = {"from_attributes": True}


class AgencyDashboardOut(BaseModel):
    managed_workspace_count: int
    total_agents: int
    total_live_agents: int
    total_runs_last_7d: int
    total_escalations: int
    workspaces: list[AgencyWorkspaceSummary]


class CloneAgentRequest(BaseModel):
    source_workspace_id: uuid.UUID = Field(
        description="Workspace the source agent lives in"
    )
    source_agent_id: uuid.UUID = Field(
        description="Agent to clone"
    )
    dest_workspace_id: uuid.UUID = Field(
        description="Workspace to clone the agent into"
    )
    dest_name: str | None = Field(
        default=None,
        description="Name for the cloned agent. Defaults to '{original name} (clone)'.",
    )


class CloneAgentResult(BaseModel):
    source_agent_id: uuid.UUID
    source_workspace_id: uuid.UUID
    cloned_agent_id: uuid.UUID
    dest_workspace_id: uuid.UUID
    cloned_name: str
