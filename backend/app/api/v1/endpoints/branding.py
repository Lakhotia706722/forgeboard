"""
White-label branding endpoints — Phase 9d.

  GET   /branding          — get current workspace branding
  PATCH /branding          — update branding fields [owner, admin, managing agency]
  PATCH /branding/agency   — assign/clear the managing agency user [owner only]
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Body

from app.api.deps import CurrentUser, CurrentWorkspace, DB
from app.schemas.branding import BrandingOut, BrandingUpdate
from app.services import branding_service

router = APIRouter()


@router.get("", response_model=BrandingOut)
async def get_branding(workspace: CurrentWorkspace, db: DB):
    """Return the current workspace's branding config. Visible to all members."""
    return await branding_service.get_branding(workspace.id, db)


@router.patch("", response_model=BrandingOut)
async def update_branding(
    body: BrandingUpdate,
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
):
    """
    Update white-label branding for this workspace.
    Allowed for: workspace owner, admin, or the assigned managing agency user.
    """
    result = await branding_service.update_branding(workspace.id, user.id, body, db)
    await db.commit()
    return result


@router.patch("/agency", response_model=BrandingOut)
async def set_managing_agency(
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    agency_user_id: uuid.UUID | None = Body(
        default=None,
        embed=True,
        description="UUID of the agency user to assign, or null to clear.",
    ),
):
    """
    Assign or clear the agency user who manages this workspace's branding.
    Only the workspace owner can do this.
    """
    result = await branding_service.set_managing_agency(
        workspace.id, agency_user_id, user.id, db
    )
    await db.commit()
    return result
