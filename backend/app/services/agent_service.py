"""
Agent business logic: CRUD, status transitions, agent config compilation.

The most important function here is build_agent_config() — it takes an agent's
goal and connected connectors and produces the AgentConfig object that Phase 4
feeds directly to Claude. Getting this schema right in Phase 3 means Phase 4
only needs to execute, not re-design.
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent, AgentConnector, AgentStatus, TriggerType
from app.models.connector import Connector, ConnectorStatus, ConnectorType
from app.schemas.agent import (
    AgentConfig,
    AgentCreate,
    AgentOut,
    AgentUpdate,
    ConnectorSummary,
    ToolDefinition,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_agent(
    agent_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> Agent:
    result = await db.execute(
        select(Agent)
        .where(Agent.id == agent_id, Agent.workspace_id == workspace_id)
        .options(
            selectinload(Agent.connector_links).selectinload(AgentConnector.connector)
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found.")
    return agent


def _to_out(agent: Agent) -> AgentOut:
    connectors = [
        ConnectorSummary(
            id=link.connector.id,
            name=link.connector.name,
            connector_type=link.connector.connector_type.value,
            status=link.connector.status.value,
        )
        for link in agent.connector_links
        if link.connector is not None
    ]
    return AgentOut(
        id=agent.id,
        workspace_id=agent.workspace_id,
        name=agent.name,
        goal=agent.goal,
        status=agent.status,
        trigger_type=agent.trigger_type,
        cron_schedule=agent.cron_schedule,
        requires_approval=agent.requires_approval,
        total_runs=agent.total_runs,
        total_cost_usd_cents=agent.total_cost_usd_cents,
        consecutive_failures=agent.consecutive_failures,
        connectors=connectors,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


# ---------------------------------------------------------------------------
# Tool definitions per connector type
# These are what get sent to Claude as the "tools" array.
# ---------------------------------------------------------------------------

def _tools_for_connector(connector: Connector) -> list[ToolDefinition]:
    """Return the MCP-style tool definitions for a given connector."""
    ctype = connector.connector_type

    if ctype == ConnectorType.HTTP_WEBHOOK:
        return [
            ToolDefinition(
                name="http_request",
                description=(
                    "Make an HTTP request to an external URL. "
                    "Use this to call webhooks, REST APIs, or any HTTP endpoint."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                            "description": "HTTP method",
                        },
                        "url": {
                            "type": "string",
                            "description": "Full URL to request",
                        },
                        "headers": {
                            "type": "object",
                            "description": "Optional HTTP headers as key-value pairs",
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional request body (JSON string or plain text)",
                        },
                    },
                    "required": ["method", "url"],
                },
            )
        ]

    elif ctype == ConnectorType.GOOGLE_CALENDAR:
        return [
            ToolDefinition(
                name="calendar_list_events",
                description="List upcoming events from Google Calendar.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of events to return (default 10)",
                            "default": 10,
                        },
                        "time_min": {
                            "type": "string",
                            "description": "Start of time range in ISO 8601 format. Defaults to now.",
                        },
                        "time_max": {
                            "type": "string",
                            "description": "End of time range in ISO 8601 format.",
                        },
                        "query": {
                            "type": "string",
                            "description": "Free-text search term to filter events.",
                        },
                    },
                    "required": [],
                },
            ),
            ToolDefinition(
                name="calendar_create_event",
                description="Create a new event in Google Calendar.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Event title"},
                        "description": {"type": "string", "description": "Event description"},
                        "start_datetime": {
                            "type": "string",
                            "description": "Start time in ISO 8601 format",
                        },
                        "end_datetime": {
                            "type": "string",
                            "description": "End time in ISO 8601 format",
                        },
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of attendee email addresses",
                        },
                    },
                    "required": ["summary", "start_datetime", "end_datetime"],
                },
            ),
        ]

    elif ctype == ConnectorType.GMAIL:
        return [
            ToolDefinition(
                name="gmail_send",
                description="Send an email via Gmail.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Recipient email address",
                        },
                        "subject": {"type": "string", "description": "Email subject line"},
                        "body": {
                            "type": "string",
                            "description": "Email body — plain text or basic HTML",
                        },
                        "cc": {
                            "type": "string",
                            "description": "Optional CC email address",
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
            )
        ]

    elif ctype == ConnectorType.KV_STORE:
        return [
            ToolDefinition(
                name="kv_get",
                description="Read a value from the notes store by key.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "The key to look up"},
                    },
                    "required": ["key"],
                },
            ),
            ToolDefinition(
                name="kv_set",
                description="Write or update a value in the notes store.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "The key to set"},
                        "value": {"type": "string", "description": "The value to store"},
                    },
                    "required": ["key", "value"],
                },
            ),
            ToolDefinition(
                name="kv_delete",
                description="Delete a key from the notes store.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "The key to delete"},
                    },
                    "required": ["key"],
                },
            ),
        ]

    return []


# ---------------------------------------------------------------------------
# Agent config builder — core of Phase 3
# ---------------------------------------------------------------------------

def build_agent_config(agent: Agent, connectors: list[Connector]) -> AgentConfig:
    """
    Compile the agent's goal + connectors into the AgentConfig object that
    the Phase 4 orchestration engine consumes directly.

    System prompt structure:
      1. Role framing
      2. The user's goal (verbatim)
      3. Operational constraints
      4. Available tools summary
    """
    tool_list = []
    connector_map: dict[str, dict] = {}

    for conn in connectors:
        tools = _tools_for_connector(conn)
        # Namespace tool names by connector id to avoid collisions
        # e.g. "kv_get" becomes "kv_get" (only one KV store per workspace)
        # but http_request could appear multiple times if user adds two HTTP connectors
        for tool in tools:
            if len(connectors) > 1:
                namespaced_name = f"{tool.name}__{str(conn.id)[:8]}"
            else:
                namespaced_name = tool.name
            tool_list.append(
                ToolDefinition(
                    name=namespaced_name,
                    description=f"[{conn.name}] {tool.description}",
                    input_schema=tool.input_schema,
                )
            )

        config_data = {}
        if conn.config_json:
            try:
                config_data = json.loads(conn.config_json)
            except json.JSONDecodeError:
                pass

        connector_map[str(conn.id)] = {
            "type": conn.connector_type.value,
            "name": conn.name,
            "config": config_data,
            # encrypted_credentials intentionally NOT included here —
            # Phase 4 fetches them fresh from DB at execution time
        }

    tool_names = ", ".join(t.name for t in tool_list) if tool_list else "none"

    system_prompt = f"""You are an autonomous AI agent built on ForgeBoard.

## Your Goal
{agent.goal}

## Operating Instructions
- Work through the goal step by step.
- Use the available tools to take actions — do not just describe what you would do.
- If a tool call fails, retry once with adjusted parameters before giving up.
- When the goal is complete, summarise what was done concisely.
- If you cannot complete the goal with the available tools, explain why clearly.
- Never hallucinate tool results — only report what tools actually return.

## Available Tools
{tool_names}

## Constraints
- Maximum 20 tool calls per run to prevent runaway execution.
- Do not store or transmit sensitive data beyond what the goal requires.
"""

    return AgentConfig(
        agent_id=str(agent.id),
        workspace_id=str(agent.workspace_id),
        system_prompt=system_prompt,
        tools=tool_list,
        connector_map=connector_map,
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_agents(workspace_id: uuid.UUID, db: AsyncSession) -> list[AgentOut]:
    result = await db.execute(
        select(Agent)
        .where(Agent.workspace_id == workspace_id)
        .options(
            selectinload(Agent.connector_links).selectinload(AgentConnector.connector)
        )
        .order_by(Agent.created_at.desc())
    )
    return [_to_out(a) for a in result.scalars().all()]


async def get_agent(
    agent_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> AgentOut:
    agent = await _load_agent(agent_id, workspace_id, db)
    return _to_out(agent)


async def create_agent(
    workspace_id: uuid.UUID, data: AgentCreate, db: AsyncSession
) -> AgentOut:
    # Validate connector ownership
    connectors = await _fetch_and_validate_connectors(
        data.connector_ids, workspace_id, db
    )

    # Validate cron if scheduled
    if data.trigger_type == TriggerType.SCHEDULED:
        if not data.cron_schedule:
            raise HTTPException(
                status_code=422,
                detail="cron_schedule is required for scheduled trigger type.",
            )
        _validate_cron(data.cron_schedule)

    agent = Agent(
        workspace_id=workspace_id,
        name=data.name,
        goal=data.goal,
        trigger_type=data.trigger_type,
        cron_schedule=data.cron_schedule,
        requires_approval=data.requires_approval,
        status=AgentStatus.DRAFT,
    )
    db.add(agent)
    await db.flush()  # get agent.id

    # Create connector links
    for conn in connectors:
        link = AgentConnector(agent_id=agent.id, connector_id=conn.id)
        db.add(link)

    # Build and store agent config
    config = build_agent_config(agent, connectors)
    agent.agent_config_json = config.model_dump_json()

    await db.flush()
    # Reload with relationships for the response
    return await get_agent(agent.id, workspace_id, db)


async def update_agent(
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    data: AgentUpdate,
    db: AsyncSession,
) -> AgentOut:
    agent = await _load_agent(agent_id, workspace_id, db)

    if data.name is not None:
        agent.name = data.name
    if data.goal is not None:
        agent.goal = data.goal
    if data.trigger_type is not None:
        agent.trigger_type = data.trigger_type
    if data.cron_schedule is not None:
        agent.cron_schedule = data.cron_schedule
        _validate_cron(data.cron_schedule)
    if data.requires_approval is not None:
        agent.requires_approval = data.requires_approval

    # Update connectors if provided
    connectors: list[Connector] = []
    if data.connector_ids is not None:
        connectors = await _fetch_and_validate_connectors(
            data.connector_ids, workspace_id, db
        )
        # Delete existing links
        for link in agent.connector_links:
            await db.delete(link)
        await db.flush()
        # Re-create
        for conn in connectors:
            db.add(AgentConnector(agent_id=agent.id, connector_id=conn.id))
    else:
        # Use existing connectors for config rebuild
        connectors = [link.connector for link in agent.connector_links if link.connector]

    # Rebuild config whenever agent is updated
    config = build_agent_config(agent, connectors)
    agent.agent_config_json = config.model_dump_json()

    await db.flush()
    return await get_agent(agent.id, workspace_id, db)


async def update_agent_status(
    agent_id: uuid.UUID,
    workspace_id: uuid.UUID,
    new_status: AgentStatus,
    db: AsyncSession,
) -> AgentOut:
    agent = await _load_agent(agent_id, workspace_id, db)
    _validate_status_transition(agent.status, new_status)
    agent.status = new_status
    await db.flush()
    return _to_out(agent)


async def delete_agent(
    agent_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> None:
    agent = await _load_agent(agent_id, workspace_id, db)
    await db.delete(agent)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

async def _fetch_and_validate_connectors(
    connector_ids: list[uuid.UUID],
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> list[Connector]:
    if not connector_ids:
        return []
    result = await db.execute(
        select(Connector).where(
            Connector.id.in_(connector_ids),
            Connector.workspace_id == workspace_id,
        )
    )
    found = result.scalars().all()
    if len(found) != len(connector_ids):
        found_ids = {str(c.id) for c in found}
        missing = [str(cid) for cid in connector_ids if str(cid) not in found_ids]
        raise HTTPException(
            status_code=422,
            detail=f"Connectors not found or not in this workspace: {missing}",
        )
    return list(found)


def _validate_cron(expr: str) -> None:
    """Basic cron expression validation (5-field standard cron)."""
    parts = expr.strip().split()
    if len(parts) != 5:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid cron expression '{expr}'. "
                "Expected 5 fields: minute hour day-of-month month day-of-week"
            ),
        )


# Status transition guard — enforces the Kanban flow rules
_ALLOWED_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
    AgentStatus.DRAFT:        {AgentStatus.TESTING, AgentStatus.PAUSED},
    AgentStatus.TESTING:      {AgentStatus.LIVE, AgentStatus.DRAFT, AgentStatus.PAUSED},
    AgentStatus.LIVE:         {AgentStatus.PAUSED, AgentStatus.NEEDS_REVIEW},
    AgentStatus.PAUSED:       {AgentStatus.DRAFT, AgentStatus.TESTING, AgentStatus.LIVE},
    AgentStatus.NEEDS_REVIEW: {AgentStatus.PAUSED, AgentStatus.TESTING, AgentStatus.LIVE},
}


def _validate_status_transition(current: AgentStatus, new: AgentStatus) -> None:
    if new == current:
        return
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if new not in allowed:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Cannot move agent from '{current}' to '{new}'. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            ),
        )
