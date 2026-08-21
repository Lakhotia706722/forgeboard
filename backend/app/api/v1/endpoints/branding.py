"""
White-label branding endpoints — Phase 9d.

  GET   /branding          — get current workspace branding
  PATCH /branding          — update branding fields [owner, admin, managing agency]
  PATCH /branding/agency   — assign/clear the managing agency user [owner only]
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Request

from app.api.deps import CurrentUser, CurrentWorkspace, DB
from app.schemas.branding import BrandingOut, BrandingUpdate
from app.services import branding_service
from app.services.platform_audit_service import log_event

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
    request: Request,
):
    before = await branding_service.get_branding(workspace.id, db)
    result = await branding_service.update_branding(workspace.id, user.id, body, db)
    await log_event(
        db=db,
        event_type="settings.branding_updated",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="workspace",
        resource_id=workspace.id,
        before_state={
            "brand_logo_url": before.brand_logo_url,
            "brand_primary_color": before.brand_primary_color,
            "brand_app_name": before.brand_app_name,
        },
        after_state={
            "brand_logo_url": result.brand_logo_url,
            "brand_primary_color": result.brand_primary_color,
            "brand_app_name": result.brand_app_name,
        },
        request=request,
    )
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
