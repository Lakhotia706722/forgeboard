"""
Agency service — Phase 9c.

An agency user holds workspace_members rows with role='agency' across
multiple client workspaces.  This service provides:

  1. list_managed_workspaces()  — all workspaces where user has agency role
  2. get_agency_dashboard()     — aggregate stats across those workspaces
  3. clone_agent()              — copy an agent config into another workspace
"""
import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent, AgentConnector, AgentStatus
from app.models.run import AgentRun, RunStatus
from app.models.user import Workspace, WorkspaceMember, WorkspaceRole, WorkspaceMemberStatus
from app.models.voice_agent import CallLog, VoiceAgent
from app.schemas.agency import (
    AgencyDashboardOut,
    AgencyWorkspaceSummary,
    CloneAgentRequest,
    CloneAgentResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Managed workspace list
# ---------------------------------------------------------------------------

async def list_managed_workspaces(
    agency_user_id: uuid.UUID,
    db: AsyncSession,
) -> list[AgencyWorkspaceSummary]:
    """
    Return all workspaces where the user has role=agency (or owner/admin).
    Agency users see workspaces they are agency members of.
    """
    result = await db.execute(
        select(WorkspaceMember)
        .where(
            WorkspaceMember.user_id == agency_user_id,
            WorkspaceMember.role == WorkspaceRole.AGENCY,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
        .options(selectinload(WorkspaceMember.workspace))
    )
    memberships = result.scalars().all()

    summaries = []
    for m in memberships:
        ws = m.workspace
        if not ws or not ws.is_active:
            continue

        # Agent count
        agent_count_r = await db.execute(
            select(func.count()).where(Agent.workspace_id == ws.id)
        )
        agent_count = agent_count_r.scalar() or 0

        # Live agent count
        live_count_r = await db.execute(
            select(func.count()).where(
                Agent.workspace_id == ws.id,
                Agent.status == AgentStatus.LIVE,
            )
        )
        live_count = live_count_r.scalar() or 0

        summaries.append(AgencyWorkspaceSummary(
            workspace_id=ws.id,
            workspace_name=ws.name,
            workspace_slug=ws.slug,
            agent_count=agent_count,
            live_agent_count=live_count,
        ))

    return summaries


# ---------------------------------------------------------------------------
# Aggregate dashboard
# ---------------------------------------------------------------------------

async def get_agency_dashboard(
    agency_user_id: uuid.UUID,
    db: AsyncSession,
) -> AgencyDashboardOut:
    """
    Aggregate stats across all workspaces the agency user manages.
    """
    # Get managed workspace IDs
    mem_result = await db.execute(
        select(WorkspaceMember.workspace_id)
        .where(
            WorkspaceMember.user_id == agency_user_id,
            WorkspaceMember.role == WorkspaceRole.AGENCY,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    ws_ids = [r for r in mem_result.scalars().all()]

    if not ws_ids:
        return AgencyDashboardOut(
            managed_workspace_count=0,
            total_agents=0,
            total_live_agents=0,
            total_runs_last_7d=0,
            total_escalations=0,
            workspaces=[],
        )

    # Aggregate counts
    total_agents_r = await db.execute(
        select(func.count()).where(Agent.workspace_id.in_(ws_ids))
    )
    total_agents = total_agents_r.scalar() or 0

    live_agents_r = await db.execute(
        select(func.count()).where(
            Agent.workspace_id.in_(ws_ids),
            Agent.status == AgentStatus.LIVE,
        )
    )
    total_live_agents = live_agents_r.scalar() or 0

    from datetime import timedelta
    since = datetime.now(timezone.utc) - timedelta(days=7)
    runs_r = await db.execute(
        select(func.count()).where(
            AgentRun.workspace_id.in_(ws_ids),
            AgentRun.created_at >= since,
        )
    )
    total_runs_7d = runs_r.scalar() or 0

    # Voice escalations across managed workspaces
    esc_r = await db.execute(
        select(func.sum(VoiceAgent.total_escalations))
        .where(VoiceAgent.workspace_id.in_(ws_ids))
    )
    total_escalations = esc_r.scalar() or 0

    # Per-workspace summaries
    workspaces = await list_managed_workspaces(agency_user_id, db)

    return AgencyDashboardOut(
        managed_workspace_count=len(ws_ids),
        total_agents=total_agents,
        total_live_agents=total_live_agents,
        total_runs_last_7d=total_runs_7d,
        total_escalations=total_escalations,
        workspaces=workspaces,
    )


# ---------------------------------------------------------------------------
# Clone agent across workspaces
# ---------------------------------------------------------------------------

async def clone_agent(
    request: CloneAgentRequest,
    agency_user_id: uuid.UUID,
    db: AsyncSession,
) -> CloneAgentResult:
    """
    Copy an agent's config from one workspace into another.

    The clone:
      - Copies name, goal, trigger_type, cron_schedule, requires_approval
      - Does NOT copy run history, cost counters, or consecutive_failures
      - Starts in DRAFT status in the destination workspace
      - Connector links are NOT copied — connectors are workspace-scoped and
        different workspaces have different connector setups

    The agency user must have agency role in BOTH source and destination workspaces.
    """
    # Verify access to source workspace
    await _assert_agency_access(agency_user_id, request.source_workspace_id, db)
    # Verify access to destination workspace
    await _assert_agency_access(agency_user_id, request.dest_workspace_id, db)

    # Load source agent
    agent_r = await db.execute(
        select(Agent).where(
            Agent.id == request.source_agent_id,
            Agent.workspace_id == request.source_workspace_id,
        )
    )
    source = agent_r.scalar_one_or_none()
    if not source:
        raise HTTPException(
            status_code=404,
            detail="Source agent not found in that workspace.",
        )

    # Create clone in destination workspace
    clone = Agent(
        workspace_id=request.dest_workspace_id,
        name=request.dest_name or f"{source.name} (clone)",
        goal=source.goal,
        trigger_type=source.trigger_type,
        cron_schedule=source.cron_schedule,
        requires_approval=source.requires_approval,
        status=AgentStatus.DRAFT,
        # agent_config_json starts empty — will be built when connectors are added
        agent_config_json=None,
    )
    db.add(clone)
    await db.flush()

    return CloneAgentResult(
        source_agent_id=source.id,
        source_workspace_id=request.source_workspace_id,
        cloned_agent_id=clone.id,
        dest_workspace_id=request.dest_workspace_id,
        cloned_name=clone.name,
    )


async def _assert_agency_access(
    agency_user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Raise 403 if user does not have agency (or owner/admin) role in workspace."""
    result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.user_id == agency_user_id,
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.role.in_([
                WorkspaceRole.AGENCY,
                WorkspaceRole.OWNER,
                WorkspaceRole.ADMIN,
            ]),
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail=f"You do not have agency access to workspace {workspace_id}.",
        )
