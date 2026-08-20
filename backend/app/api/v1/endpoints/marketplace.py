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

from fastapi import APIRouter, Depends, Query
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
    db: DB,
):
    """
    Install a marketplace listing into the active workspace.
    Creates an Agent (Draft) or Connector (PendingAuth) as an independent copy.
    """
    result = await marketplace_service.install_listing(listing_id, workspace.id, db)
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
):
    """
    Submit a new listing for admin review.

    The config payload is scanned for credential-like content before entering
    the review queue. Returns 422 if credentials are detected.
    """
    result = await marketplace_service.submit_listing(
        data=body,
        author_user_id=user.id,
        author_name=user.full_name,
        db=db,
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
):
    """
    Approve or reject a pending listing.
    Rejected listings notify the submitter with the review note.
    Requires owner or admin role.
    """
    result = await marketplace_service.review_listing(
        listing_id=listing_id,
        reviewer_user_id=user.id,
        action=body,
        db=db,
    )
    await db.commit()
    return result
