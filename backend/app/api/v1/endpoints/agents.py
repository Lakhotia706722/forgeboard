"""
Agent endpoints:
  GET    /agents              — list workspace agents  [all roles]
  POST   /agents              — create agent           [builder, admin, owner]
  GET    /agents/{id}         — get agent              [all roles]
  PATCH  /agents/{id}         — update agent fields    [builder, admin, owner]
  DELETE /agents/{id}         — delete agent           [builder, admin, owner]
  PATCH  /agents/{id}/status  — update Kanban status   [builder, admin, owner]
  GET    /agents/{id}/config  — return compiled config [all roles]
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentWorkspace, DB, require_role
from app.models.agent import AgentStatus
from app.schemas.agent import AgentConfig, AgentCreate, AgentOut, AgentStatusUpdate, AgentUpdate
from app.services import agent_service
import json

router = APIRouter()

_BUILDER_UP = require_role("owner", "admin", "builder")
_ADMIN_UP   = require_role("owner", "admin")


@router.get("", response_model=list[AgentOut])
async def list_agents(workspace: CurrentWorkspace, db: DB):
    return await agent_service.list_agents(workspace.id, db)


@router.post("", response_model=AgentOut, status_code=201)
async def create_agent(
    body: AgentCreate,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    """
    Create a new agent in Draft status.
    Validates connector ownership, builds the system prompt + tool config,
    and stores the compiled AgentConfig for Phase 4.
    """
    return await agent_service.create_agent(workspace.id, body, db)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: uuid.UUID, workspace: CurrentWorkspace, db: DB):
    return await agent_service.get_agent(agent_id, workspace.id, db)


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    """Partial update — only provided fields are changed. Rebuilds agent config."""
    return await agent_service.update_agent(agent_id, workspace.id, body, db)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    await agent_service.delete_agent(agent_id, workspace.id, db)


@router.patch("/{agent_id}/status", response_model=AgentOut)
async def update_agent_status(
    agent_id: uuid.UUID,
    body: AgentStatusUpdate,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    """
    Move an agent between Kanban lanes.
    Validates allowed status transitions (e.g. can't go Draft → Live directly).
    Moving to Live enables scheduled/webhook triggers.
    Moving to Paused halts triggers.
    """
    return await agent_service.update_agent_status(
        agent_id, workspace.id, body.status, db
    )


@router.get("/{agent_id}/config", response_model=AgentConfig)
async def get_agent_config(agent_id: uuid.UUID, workspace: CurrentWorkspace, db: DB):
    """
    Return the compiled AgentConfig for inspection / Phase 4 preview.
    Useful for debugging the system prompt and tool definitions.
    """
    agent_out = await agent_service.get_agent(agent_id, workspace.id, db)
    # Load raw agent to get config JSON
    from sqlalchemy import select
    from app.models.agent import Agent
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.workspace_id == workspace.id)
    )
    agent = result.scalar_one_or_none()
    if not agent or not agent.agent_config_json:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Agent config not yet built.")
    return AgentConfig.model_validate_json(agent.agent_config_json)
