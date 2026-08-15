"""
Agency endpoints — Phase 9c.

These endpoints are for users with role='agency' in one or more workspaces.
They operate OUTSIDE the normal X-Workspace-ID scoping — the agency user
queries across multiple workspaces they manage.

  GET  /agency/workspaces        — list all workspaces the agency user manages
  GET  /agency/dashboard         — aggregate stats across managed workspaces
  POST /agency/clone-agent       — clone an agent config into another workspace

Authentication: standard Bearer token.
Authorization: each endpoint verifies the user has agency/owner/admin role
               in the target workspace(s) via the service layer.
"""
from fastapi import APIRouter

from app.api.deps import CurrentUser, DB
from app.schemas.agency import (
    AgencyDashboardOut,
    AgencyWorkspaceSummary,
    CloneAgentRequest,
    CloneAgentResult,
)
from app.services import agency_service

router = APIRouter()


@router.get("/workspaces", response_model=list[AgencyWorkspaceSummary])
async def list_managed_workspaces(user: CurrentUser, db: DB):
    """
    List all workspaces the authenticated user has agency role in.
    Returns workspace name, slug, and basic agent counts.
    """
    return await agency_service.list_managed_workspaces(user.id, db)


@router.get("/dashboard", response_model=AgencyDashboardOut)
async def agency_dashboard(user: CurrentUser, db: DB):
    """
    Aggregate view across all managed workspaces:
    total agents, live agents, runs in the last 7 days, voice escalations.
    Returns an empty dashboard (zeros) if the user has no agency memberships.
    """
    return await agency_service.get_agency_dashboard(user.id, db)


@router.post("/clone-agent", response_model=CloneAgentResult, status_code=201)
async def clone_agent(body: CloneAgentRequest, user: CurrentUser, db: DB):
    """
    Clone an agent's config from one workspace into another.

    Copies: name, goal, trigger_type, cron_schedule, requires_approval.
    Does NOT copy: run history, connectors, cost counters.
    The clone starts in DRAFT status.

    The calling user must have agency|admin|owner role in BOTH workspaces.
    """
    result = await agency_service.clone_agent(body, user.id, db)
    await db.commit()
    return result
