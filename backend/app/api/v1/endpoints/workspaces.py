"""
Workspace management endpoints — Phase 9b.

  GET    /workspaces/me              — current workspace detail + settings
  PATCH  /workspaces/me              — update workspace settings [owner, admin]
  GET    /workspaces/me/members      — list members [all roles]
  POST   /workspaces/me/members      — invite a member [owner, admin]
  PATCH  /workspaces/me/members/{user_id}  — change role [owner, admin]
  DELETE /workspaces/me/members/{user_id}  — remove member [owner, admin]

Permission matrix:
  owner  — full control: invite, remove, change roles, update settings
  admin  — invite, remove (non-owner), change roles (non-owner), update settings
  builder — read members, create/edit/delete agents and connectors (enforced per endpoint)
  viewer  — read-only: cannot create/edit/delete agents, connectors, etc.
  agency  — read + cross-workspace aggregate views (Phase 9c)

Role enforcement on existing endpoints:
  Agents create/update/delete  → builder, admin, owner
  Connectors create/delete     → admin, owner
  Governance spend-cap update  → admin, owner
  Audit log view               → viewer, builder, admin, owner (all)
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import (
    CurrentUser,
    CurrentWorkspace,
    DB,
    require_role,
)
from app.schemas.workspaces import (
    MemberInvite,
    MemberOut,
    MemberRoleUpdate,
    WorkspaceDetailOut,
    WorkspaceSettingsUpdate,
)
from app.services import workspace_service

router = APIRouter()

# Role shorthand aliases for readability
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
    """Return the current workspace's settings."""
    return await workspace_service.get_workspace_detail(workspace.id, db)


@router.patch("/me", response_model=WorkspaceDetailOut)
async def update_workspace(
    body: WorkspaceSettingsUpdate,
    _: Annotated[None, _OWNER_ADMIN],
    workspace: CurrentWorkspace,
    db: DB,
):
    """Update workspace name, description, or spend cap. Requires owner or admin."""
    result = await workspace_service.update_workspace_settings(workspace.id, body, db)
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
    """List all workspace members (active + pending). Visible to all roles."""
    return await workspace_service.list_members(workspace.id, db)


@router.post("/me/members", response_model=MemberOut, status_code=201)
async def invite_member(
    body: MemberInvite,
    _: Annotated[None, _OWNER_ADMIN],
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
):
    """
    Invite a user by email. Creates a pending WorkspaceMember row.
    The invitee sees the invite banner on their next login and accepts in-app.
    Requires owner or admin role.
    """
    result = await workspace_service.invite_member(
        workspace_id=workspace.id,
        invited_by_user_id=user.id,
        data=body,
        db=db,
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
):
    """Change a member's role. Cannot change owner role or assign owner."""
    result = await workspace_service.update_member_role(
        workspace_id=workspace.id,
        target_user_id=target_user_id,
        requesting_user_id=user.id,
        data=body,
        db=db,
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
):
    """Remove a member from the workspace. Cannot remove owner or yourself."""
    await workspace_service.remove_member(
        workspace_id=workspace.id,
        target_user_id=target_user_id,
        requesting_user_id=user.id,
        db=db,
    )
    await db.commit()
