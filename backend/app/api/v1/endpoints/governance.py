"""
Governance endpoints:
  GET  /governance/audit              — list audit log entries        [all roles]
  GET  /governance/audit/export       — export as JSON or CSV         [admin, owner]
  GET  /governance/spend              — current spend vs cap          [all roles]
  PATCH /governance/spend-cap         — update workspace spend cap    [admin, owner]
  GET  /governance/pending-approvals  — agents awaiting approval      [all roles]
"""
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import PlainTextResponse, Response

from app.api.deps import CurrentUser, CurrentWorkspace, DB, require_role
from app.services import governance_service
from app.services.platform_audit_service import log_event

router = APIRouter()

_ADMIN_UP = require_role("owner", "admin")


@router.get("/audit")
async def list_audit_log(
    workspace: CurrentWorkspace,
    db: DB,
    agent_id: Optional[uuid.UUID] = Query(default=None),
    run_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=200, le=1000),
):
    entries = await governance_service.list_audit_log(
        workspace.id, db, agent_id=agent_id, run_id=run_id, limit=limit
    )
    return [
        {
            "id": str(e.id),
            "agent_id": str(e.agent_id),
            "run_id": str(e.run_id),
            "agent_name": e.agent_name,
            "tool_name": e.tool_name,
            "tool_input": governance_service._safe_json(e.tool_input_json),
            "tool_result": governance_service._safe_json(e.tool_result_json),
            "outcome": e.outcome,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.get("/audit/export")
async def export_audit_log(
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    agent_id: Optional[uuid.UUID] = Query(default=None),
    limit: int = Query(default=1000, le=5000),
):
    """Export audit log as JSON or CSV download. Requires admin or owner."""
    entries = await governance_service.list_audit_log(
        workspace.id, db, agent_id=agent_id, limit=limit
    )

    if format == "csv":
        content = governance_service.export_audit_csv(entries)
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=audit_log.csv"},
        )

    content = governance_service.export_audit_json(entries)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=audit_log.json"},
    )


@router.get("/spend")
async def get_spend(workspace: CurrentWorkspace, db: DB):
    """Return current spend vs cap for the workspace."""
    return await governance_service.get_workspace_spend(workspace.id, db)


@router.patch("/spend-cap")
async def update_spend_cap(
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    request: Request,
    cap_usd_cents: int = Query(
        ...,
        ge=0,
        description="New spend cap in USD cents (e.g. 5000 = $50.00)",
    ),
):
    """Update the hard spend cap. Requires admin or owner."""
    before = await governance_service.get_workspace_spend(workspace.id, db)
    result = await governance_service.update_spend_cap(workspace.id, cap_usd_cents, db)
    await log_event(
        db=db,
        event_type="settings.spend_cap_changed",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="workspace",
        resource_id=workspace.id,
        before_state={"spend_cap_usd_cents": before["spend_cap_usd_cents"]},
        after_state={"spend_cap_usd_cents": cap_usd_cents},
        request=request,
    )
    return result


@router.get("/pending-approvals")
async def list_pending_approvals(workspace: CurrentWorkspace, db: DB):
    """Return agents with requires_approval=True that have active runs."""
    return await governance_service.list_pending_approvals(workspace.id, db)


# ---------------------------------------------------------------------------
# Platform audit log — Phase 11a
# ---------------------------------------------------------------------------

@router.get("/platform-audit")
async def list_platform_audit(
    workspace: CurrentWorkspace,
    db: DB,
    event_type: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=2000),
    offset: int = Query(default=0, ge=0),
):
    """
    Query the platform-wide audit log for this workspace.
    Covers membership changes, settings updates, marketplace events, etc.
    Visible to all workspace roles.
    """
    from sqlalchemy import select
    from app.models.platform_audit import PlatformAuditLog

    q = select(PlatformAuditLog).where(
        PlatformAuditLog.workspace_id == workspace.id
    )
    if event_type:
        q = q.where(PlatformAuditLog.event_type == event_type)
    q = q.order_by(PlatformAuditLog.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(q)
    entries = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "actor_email": e.actor_email,
            "actor_name": e.actor_name,
            "resource_type": e.resource_type,
            "resource_id": str(e.resource_id) if e.resource_id else None,
            "before_state": e.before_state,
            "after_state": e.after_state,
            "ip_address": e.ip_address,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


@router.get("/platform-audit/export")
async def export_platform_audit(
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    limit: int = Query(default=5000, le=50000),
):
    """
    Export the full platform audit log. Requires admin or owner.
    Supports JSON and CSV formats.
    """
    from sqlalchemy import select
    from app.models.platform_audit import PlatformAuditLog
    from app.services.platform_audit_service import (
        export_platform_audit_csv,
        export_platform_audit_json,
    )

    result = await db.execute(
        select(PlatformAuditLog)
        .where(PlatformAuditLog.workspace_id == workspace.id)
        .order_by(PlatformAuditLog.created_at.desc())
        .limit(limit)
    )
    entries = list(result.scalars().all())

    if format == "csv":
        content = export_platform_audit_csv(entries)
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=platform_audit.csv"},
        )
    content = export_platform_audit_json(entries)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=platform_audit.json"},
    )
