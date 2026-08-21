"""
Marketplace endpoints — Phase 10.

Public catalog (no auth required):
  GET  /marketplace                  — browse approved listings
  GET  /marketplace/categories       — list distinct categories
  GET  /marketplace/{id}             — get listing detail + config payload

Authenticated:
  POST /marketplace/{id}/install     — install into active workspace [all roles]
  POST /marketplace/submit           — submit a new listing for review
  GET  /marketplace/my/submissions   — author's own listings (all statuses)
  GET  /marketplace/my/stats         — install + revenue summary

Admin review queue [admin, owner]:
  GET  /marketplace/admin/pending    — pending submissions
  POST /marketplace/admin/{id}/review — approve or reject
"""
import uuid

from fastapi import APIRouter, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated, Optional

from app.api.deps import CurrentUser, CurrentWorkspace, DB, require_role
from app.schemas.marketplace import (
    InstallResult,
    ListingDetail,
    ListingOut,
    ListingSubmit,
    ReviewAction,
)
from app.services import marketplace_service
from app.services.platform_audit_service import log_event
from app.models.marketplace import ListingType

router = APIRouter()

# Optional auth bearer — used for public endpoints that work with or without auth
_optional_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Public catalog (no auth)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ListingOut])
async def list_catalog(
    db: DB,
    q: Optional[str] = Query(default=None, description="Search name/description/category"),
    category: Optional[str] = Query(default=None),
    listing_type: Optional[ListingType] = Query(default=None),
    sort: str = Query(default="popular", pattern="^(popular|recent)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Browse the public marketplace catalog. No authentication required."""
    return await marketplace_service.list_catalog(
        db, q=q, category=category, listing_type=listing_type,
        sort=sort, limit=limit, offset=offset,
    )


@router.get("/categories", response_model=list[str])
async def list_categories(db: DB):
    """Return all distinct categories from approved listings."""
    return await marketplace_service.list_categories(db)


@router.get("/my/submissions", response_model=list[ListingDetail])
async def my_submissions(user: CurrentUser, db: DB):
    """Return all listings submitted by the current user (all statuses)."""
    from sqlalchemy import select
    from app.models.marketplace import MarketplaceListing
    result = await db.execute(
        select(MarketplaceListing)
        .where(MarketplaceListing.author_user_id == user.id)
        .order_by(MarketplaceListing.created_at.desc())
    )
    from app.services.marketplace_service import _to_detail
    return [_to_detail(l) for l in result.scalars().all()]


@router.get("/my/stats")
async def my_stats(user: CurrentUser, db: DB):
    """Author-facing install count and estimated payout. Display only — no real payments."""
    return await marketplace_service.get_author_stats(user.id, db)


@router.get("/{listing_id}", response_model=ListingDetail)
async def get_listing(listing_id: uuid.UUID, db: DB):
    """Get a single approved listing including its config payload."""
    return await marketplace_service.get_listing(listing_id, db)


# ---------------------------------------------------------------------------
# Install (authenticated, workspace-scoped)
# ---------------------------------------------------------------------------

@router.post("/{listing_id}/install", response_model=InstallResult, status_code=201)
async def install_listing(
    listing_id: uuid.UUID,
    workspace: CurrentWorkspace,
    user: CurrentUser,
    db: DB,
    request: Request,
):
    result = await marketplace_service.install_listing(listing_id, workspace.id, db)
    await log_event(
        db=db,
        event_type="marketplace.installed",
        workspace_id=workspace.id,
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="marketplace_listing",
        resource_id=listing_id,
        after_state={
            "listing_name": result.listing_name,
            "installed_type": result.installed_type.value,
            "agent_id": str(result.agent_id) if result.agent_id else None,
            "connector_id": str(result.connector_id) if result.connector_id else None,
        },
        request=request,
    )
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Submission (authenticated)
# ---------------------------------------------------------------------------

@router.post("/submit", response_model=ListingDetail, status_code=201)
async def submit_listing(
    body: ListingSubmit,
    user: CurrentUser,
    db: DB,
    request: Request,
):
    result = await marketplace_service.submit_listing(
        data=body, author_user_id=user.id, author_name=user.full_name, db=db,
    )
    await log_event(
        db=db,
        event_type="marketplace.submitted",
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="marketplace_listing",
        resource_id=result.id,
        after_state={"name": result.name, "category": result.category, "listing_type": result.listing_type.value},
        request=request,
    )
    await db.commit()
    return result


# ---------------------------------------------------------------------------
# Admin review (owner or admin role in any workspace)
# ---------------------------------------------------------------------------

@router.get("/admin/pending", response_model=list[ListingDetail])
async def list_pending(
    _: Annotated[None, require_role("owner", "admin")],
    db: DB,
):
    """Return all pending submissions awaiting review. Requires owner or admin role."""
    return await marketplace_service.list_pending_submissions(db)


@router.post("/admin/{listing_id}/review", response_model=ListingDetail)
async def review_listing(
    listing_id: uuid.UUID,
    body: ReviewAction,
    _: Annotated[None, require_role("owner", "admin")],
    user: CurrentUser,
    db: DB,
    request: Request,
):
    result = await marketplace_service.review_listing(
        listing_id=listing_id, reviewer_user_id=user.id, action=body, db=db,
    )
    await log_event(
        db=db,
        event_type=f"marketplace.{'approved' if body.action == 'approve' else 'rejected'}",
        actor_user_id=user.id,
        actor_email=user.email,
        actor_name=user.full_name,
        resource_type="marketplace_listing",
        resource_id=listing_id,
        after_state={"status": result.status.value, "review_note": body.note},
        request=request,
    )
    await db.commit()
    return result
