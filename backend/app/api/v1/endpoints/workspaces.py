"""
Workspace management endpoints — Phase 9b / 11a (audit hardening).

  GET    /workspaces/me              — current workspace detail + settings
  PATCH  /workspaces/me              — update workspace settings [owner, admin]
  GET    /workspaces/me/members      — list members [all roles]
  POST   /workspaces/me/members      — invite a member [owner, admin]
  PATCH  /workspaces/me/members/{user_id}  — change role [owner, admin]
  DELETE /workspaces/me/members/{user_id}  — remove member [owner, admin]
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, CurrentWorkspace, DB, require_role
from app.schemas.workspaces import (
    MemberInvite,
    MemberOut,
    MemberRoleUpdate,
    WorkspaceDetailOut,
    WorkspaceSettingsUpdate,
)
from app.services import workspace_service
from app.services.platform_audit_service import log_event

router = APIRouter()

_OWNER_ADMIN = require_role("owner", "admin")
_ALL_MEMBERS = require_role("owner", "admin", "builder", "viewer", "agency")


# ---------------------------------------------------------------------------
# Workspace settings
# ---------------------------------------------------------------------------

@router.get("/me", response_model=WorkspaceDetailOut)
async def get_workspace(
    _: Annotated[None, _ALL_MEMBERS],
    workspace: CurrentWorkspace,
    db: DB,
):
    return await workspace_service.get_workspace_detail(workspace.id, db)


@router.patch("/me", response_model=WorkspaceDetailOut)
async def update_workspace(
    body: WorkspaceSettingsUpdate,
    _: Annotated[None, _OWNER_ADMIN],
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    request: Request,
):
    before = await workspace_service.get_workspace_detail(workspace.id, db)
    result = await workspace_service.update_workspace_settings(workspace.id, body, db)
    await log_event(
        db=db,
        event_type="settings.workspace_updated",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="workspace",
        resource_id=workspace.id,
        before_state={
            "name": before.name,
            "description": before.description,
            "spend_cap_usd_cents": before.spend_cap_usd_cents,
        },
        after_state={
            "name": result.name,
            "description": result.description,
            "spend_cap_usd_cents": result.spend_cap_usd_cents,
        },
        request=request,
    )
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Member management
# ---------------------------------------------------------------------------

@router.get("/me/members", response_model=list[MemberOut])
async def list_members(
    _: Annotated[None, _ALL_MEMBERS],
    workspace: CurrentWorkspace,
    db: DB,
):
    return await workspace_service.list_members(workspace.id, db)


@router.post("/me/members", response_model=MemberOut, status_code=201)
async def invite_member(
    body: MemberInvite,
    _: Annotated[None, _OWNER_ADMIN],
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    request: Request,
):
    result = await workspace_service.invite_member(
        workspace_id=workspace.id,
        invited_by_user_id=user.id,
        data=body,
        db=db,
    )
    await log_event(
        db=db,
        event_type="member.invited",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="workspace_member",
        resource_id=result.user_id,
        after_state={"email": result.email, "role": result.role.value, "status": result.status.value},
        request=request,
    )
    await db.commit()
    return result


@router.patch("/me/members/{target_user_id}", response_model=MemberOut)
async def update_member_role(
    target_user_id: uuid.UUID,
    body: MemberRoleUpdate,
    _: Annotated[None, _OWNER_ADMIN],
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    request: Request,
):
    # Capture before-state
    members_before = await workspace_service.list_members(workspace.id, db)
    before_member = next((m for m in members_before if m.user_id == target_user_id), None)

    result = await workspace_service.update_member_role(
        workspace_id=workspace.id,
        target_user_id=target_user_id,
        requesting_user_id=user.id,
        data=body,
        db=db,
    )
    await log_event(
        db=db,
        event_type="member.role_changed",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="workspace_member",
        resource_id=target_user_id,
        before_state={"role": before_member.role.value} if before_member else None,
        after_state={"role": result.role.value, "email": result.email},
        request=request,
    )
    await db.commit()
    return result


@router.delete("/me/members/{target_user_id}", status_code=204)
async def remove_member(
    target_user_id: uuid.UUID,
    _: Annotated[None, _OWNER_ADMIN],
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    request: Request,
):
    members_before = await workspace_service.list_members(workspace.id, db)
    target = next((m for m in members_before if m.user_id == target_user_id), None)

    await workspace_service.remove_member(
        workspace_id=workspace.id,
        target_user_id=target_user_id,
        requesting_user_id=user.id,
        db=db,
    )
    await log_event(
        db=db,
        event_type="member.removed",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="workspace_member",
        resource_id=target_user_id,
        before_state={"email": target.email, "role": target.role.value} if target else None,
        request=request,
    )
    await db.commit()
