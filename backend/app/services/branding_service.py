"""
Branding service — Phase 9d.

Reads and writes per-workspace white-label branding fields.
Only the agency user who manages a workspace (managed_by_agency_id) or
the workspace owner/admin can update branding.
"""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Workspace, WorkspaceMember, WorkspaceRole, WorkspaceMemberStatus
from app.schemas.branding import BrandingOut, BrandingUpdate


async def get_branding(workspace_id: uuid.UUID, db: AsyncSession) -> BrandingOut:
    ws = await _load(workspace_id, db)
    return BrandingOut(
        workspace_id=ws.id,
        display_name=ws.display_name,
        brand_logo_url=ws.brand_logo_url,
        brand_primary_color=ws.brand_primary_color,
        brand_app_name=ws.brand_app_name,
        managed_by_agency_id=ws.managed_by_agency_id,
    )


async def update_branding(
    workspace_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    data: BrandingUpdate,
    db: AsyncSession,
) -> BrandingOut:
    """
    Update branding. Allowed for:
      - workspace owner/admin
      - the agency user listed in workspace.managed_by_agency_id
    """
    ws = await _load(workspace_id, db)

    # Check permission: owner/admin via workspace_members, OR the managing agency user
    is_managing_agency = (
        ws.managed_by_agency_id is not None
        and ws.managed_by_agency_id == requesting_user_id
    )

    if not is_managing_agency:
        member_r = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == requesting_user_id,
                WorkspaceMember.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
                WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
            )
        )
        if not member_r.scalar_one_or_none():
            raise HTTPException(
                status_code=403,
                detail="Only workspace owner/admin or the managing agency can update branding.",
            )

    if data.display_name is not None:
        ws.display_name = data.display_name or None
    if data.brand_logo_url is not None:
        ws.brand_logo_url = data.brand_logo_url or None
    if data.brand_primary_color is not None:
        ws.brand_primary_color = data.brand_primary_color or None
    if data.brand_app_name is not None:
        ws.brand_app_name = data.brand_app_name or None

    await db.flush()
    return BrandingOut(
        workspace_id=ws.id,
        display_name=ws.display_name,
        brand_logo_url=ws.brand_logo_url,
        brand_primary_color=ws.brand_primary_color,
        brand_app_name=ws.brand_app_name,
        managed_by_agency_id=ws.managed_by_agency_id,
    )


async def set_managing_agency(
    workspace_id: uuid.UUID,
    agency_user_id: uuid.UUID | None,
    requesting_user_id: uuid.UUID,
    db: AsyncSession,
) -> BrandingOut:
    """
    Assign or clear the agency user who manages this workspace.
    Only the workspace owner can do this.
    """
    ws = await _load(workspace_id, db)

    member_r = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == requesting_user_id,
            WorkspaceMember.role == WorkspaceRole.OWNER,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    if not member_r.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Only the workspace owner can assign an agency.")

    ws.managed_by_agency_id = agency_user_id
    await db.flush()

    return BrandingOut(
        workspace_id=ws.id,
        display_name=ws.display_name,
        brand_logo_url=ws.brand_logo_url,
        brand_primary_color=ws.brand_primary_color,
        brand_app_name=ws.brand_app_name,
        managed_by_agency_id=ws.managed_by_agency_id,
    )


async def _load(workspace_id: uuid.UUID, db: AsyncSession) -> Workspace:
    r = await db.execute(select(Workspace).where(Workspace.id == workspace_id))
    ws = r.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return ws
