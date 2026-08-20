"""
Marketplace service — Phase 10a/10b/10c/10d.

Responsibilities:
  10a  list_catalog, get_listing, seed_first_party_listings
  10b  install_listing (agent or connector)
  10c  submit_listing, review_listing
  10d  get_author_stats (install/revenue summary)

Security invariant: config_payload is NEVER allowed to contain credentials.
The credential scrubber (Phase 10c) enforces this at submission time.
First-party listings bypass the scrubber — they are seeded by engineers.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketplace import ListingStatus, ListingType, MarketplaceListing
from app.models.agent import Agent, AgentStatus, TriggerType
from app.models.connector import Connector, ConnectorStatus, ConnectorType
from app.schemas.marketplace import (
    InstallResult,
    ListingDetail,
    ListingOut,
    ListingSubmit,
    ReviewAction,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_out(listing: MarketplaceListing) -> ListingOut:
    return ListingOut(
        id=listing.id,
        name=listing.name,
        description=listing.description,
        category=listing.category,
        author_name=listing.author_name,
        listing_type=listing.listing_type,
        status=listing.status,
        version=listing.version,
        preview_image_url=listing.preview_image_url,
        install_count=listing.install_count,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
    )


def _to_detail(listing: MarketplaceListing) -> ListingDetail:
    return ListingDetail(
        id=listing.id,
        name=listing.name,
        description=listing.description,
        category=listing.category,
        author_name=listing.author_name,
        listing_type=listing.listing_type,
        status=listing.status,
        version=listing.version,
        preview_image_url=listing.preview_image_url,
        install_count=listing.install_count,
        created_at=listing.created_at,
        updated_at=listing.updated_at,
        config_payload=listing.config_payload,
    )


# ---------------------------------------------------------------------------
# 10a — Catalog
# ---------------------------------------------------------------------------

async def list_catalog(
    db: AsyncSession,
    q: str | None = None,
    category: str | None = None,
    listing_type: ListingType | None = None,
    sort: str = "popular",
    limit: int = 20,
    offset: int = 0,
) -> list[ListingOut]:
    """Return approved listings with optional search/filter."""
    query = select(MarketplaceListing).where(
        MarketplaceListing.status == ListingStatus.APPROVED
    )

    if q:
        search = f"%{q.lower()}%"
        query = query.where(
            func.lower(MarketplaceListing.name).like(search)
            | func.lower(MarketplaceListing.description).like(search)
            | func.lower(MarketplaceListing.category).like(search)
        )

    if category:
        query = query.where(MarketplaceListing.category == category)

    if listing_type:
        query = query.where(MarketplaceListing.listing_type == listing_type)

    if sort == "popular":
        query = query.order_by(MarketplaceListing.install_count.desc())
    else:
        query = query.order_by(MarketplaceListing.created_at.desc())

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return [_to_out(l) for l in result.scalars().all()]


async def get_listing(listing_id: uuid.UUID, db: AsyncSession) -> ListingDetail:
    """Return a single approved listing with its config payload."""
    result = await db.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.status == ListingStatus.APPROVED,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")
    return _to_detail(listing)


async def list_categories(db: AsyncSession) -> list[str]:
    """Return distinct categories from approved listings."""
    result = await db.execute(
        select(MarketplaceListing.category)
        .where(MarketplaceListing.status == ListingStatus.APPROVED)
        .distinct()
        .order_by(MarketplaceListing.category)
    )
    return [r for r in result.scalars().all()]


# ---------------------------------------------------------------------------
# 10b — Install
# ---------------------------------------------------------------------------

async def install_listing(
    listing_id: uuid.UUID,
    workspace_id: uuid.UUID,
    db: AsyncSession,
) -> InstallResult:
    """
    Install a marketplace listing into the calling user's active workspace.

    Agent install:
      Creates a new Agent in DRAFT status.
      Does NOT copy run history, costs, or connector IDs.
      The agent's goal and trigger config are taken from the listing payload.
      connector_map starts empty — user must link their own connectors.

    Connector install:
      Creates a Connector record pre-filled with the listing's connector_type
      and non-secret config (e.g. calendar_id).
      No credentials — user must authenticate separately.

    The listing's install_count is incremented atomically.
    Installed copies are fully independent — editing them never touches the listing.
    """
    result = await db.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.id == listing_id,
            MarketplaceListing.status == ListingStatus.APPROVED,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or not approved.")

    payload = listing.config_payload
    agent_id: uuid.UUID | None = None
    connector_id: uuid.UUID | None = None

    if listing.listing_type == ListingType.AGENT:
        # Build trigger type safely
        raw_trigger = payload.get("trigger_type", "manual")
        try:
            trigger = TriggerType(raw_trigger)
        except ValueError:
            trigger = TriggerType.MANUAL

        agent = Agent(
            workspace_id=workspace_id,
            name=payload.get("name", listing.name),
            goal=payload.get("goal", ""),
            trigger_type=trigger,
            cron_schedule=payload.get("cron_schedule"),
            requires_approval=payload.get("requires_approval", False),
            status=AgentStatus.DRAFT,
            # agent_config_json is empty — must be built once connectors are linked
            agent_config_json=None,
        )
        db.add(agent)
        await db.flush()
        agent_id = agent.id

    elif listing.listing_type == ListingType.CONNECTOR:
        import json as _json
        raw_ctype = payload.get("connector_type", "http_webhook")
        try:
            ctype = ConnectorType(raw_ctype)
        except ValueError:
            ctype = ConnectorType.HTTP_WEBHOOK

        config = payload.get("config", {})
        connector = Connector(
            workspace_id=workspace_id,
            name=payload.get("name", listing.name),
            connector_type=ctype,
            status=ConnectorStatus.PENDING_AUTH,
            config_json=_json.dumps(config) if config else None,
        )
        db.add(connector)
        await db.flush()
        connector_id = connector.id

    # Increment install counter
    listing.install_count += 1
    listing.updated_at = _now()

    return InstallResult(
        listing_id=listing.id,
        listing_name=listing.name,
        installed_type=listing.listing_type,
        agent_id=agent_id,
        connector_id=connector_id,
        workspace_id=workspace_id,
    )


# ---------------------------------------------------------------------------
# 10c — Submission & review
# ---------------------------------------------------------------------------

async def submit_listing(
    data: ListingSubmit,
    author_user_id: uuid.UUID,
    author_name: str,
    db: AsyncSession,
) -> ListingDetail:
    """
    Submit a new listing for review.

    The config_payload is scrubbed before being stored.
    Raises 422 if credential-like patterns are detected.
    """
    from app.services.credential_scrubber import scrub_payload
    cleaned, warnings = scrub_payload(data.config_payload)
    if warnings:
        raise HTTPException(
            status_code=422,
            detail=(
                "Config payload contains potential credentials or workspace-specific "
                f"identifiers and cannot be submitted: {'; '.join(warnings)}"
            ),
        )

    listing = MarketplaceListing(
        name=data.name,
        description=data.description,
        category=data.category,
        listing_type=data.listing_type,
        author_user_id=author_user_id,
        author_name=author_name,
        config_payload=cleaned,
        preview_image_url=data.preview_image_url,
        status=ListingStatus.PENDING,
    )
    db.add(listing)
    await db.flush()
    return _to_detail(listing)


async def review_listing(
    listing_id: uuid.UUID,
    reviewer_user_id: uuid.UUID,
    action: ReviewAction,
    db: AsyncSession,
) -> ListingDetail:
    """
    Approve or reject a pending listing.
    Only available to admin users (enforced at the endpoint layer).
    """
    result = await db.execute(
        select(MarketplaceListing).where(MarketplaceListing.id == listing_id)
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found.")

    if listing.status != ListingStatus.PENDING:
        raise HTTPException(
            status_code=422,
            detail=f"Listing is {listing.status.value}, not pending. Cannot review.",
        )

    if action.action == "reject" and not action.note:
        raise HTTPException(
            status_code=422,
            detail="A review note is required when rejecting a listing.",
        )

    listing.status = (
        ListingStatus.APPROVED if action.action == "approve" else ListingStatus.REJECTED
    )
    listing.review_note = action.note
    listing.reviewed_by = reviewer_user_id
    listing.reviewed_at = _now()
    listing.updated_at = _now()
    await db.flush()
    return _to_detail(listing)


async def list_pending_submissions(db: AsyncSession) -> list[ListingDetail]:
    """Return all pending submissions for the admin review queue."""
    result = await db.execute(
        select(MarketplaceListing)
        .where(MarketplaceListing.status == ListingStatus.PENDING)
        .order_by(MarketplaceListing.created_at.asc())
    )
    return [_to_detail(l) for l in result.scalars().all()]


# ---------------------------------------------------------------------------
# 10d — Author stats
# ---------------------------------------------------------------------------

async def get_author_stats(
    author_user_id: uuid.UUID,
    db: AsyncSession,
    take_rate_pct: float = 0.30,
) -> dict:
    """
    Return install count and estimated payout for an author's listings.

    take_rate_pct: the platform's take rate (default 30%).
    Revenue per install is hardcoded at $1.00 for now — no per-listing pricing yet.
    No real money movement in this phase — display only.
    """
    REVENUE_PER_INSTALL_USD = 1.00  # TODO: make configurable or per-listing

    result = await db.execute(
        select(MarketplaceListing).where(
            MarketplaceListing.author_user_id == author_user_id,
            MarketplaceListing.status == ListingStatus.APPROVED,
        )
    )
    listings = result.scalars().all()

    total_installs = sum(l.install_count for l in listings)
    gross_revenue = total_installs * REVENUE_PER_INSTALL_USD
    platform_take = gross_revenue * take_rate_pct
    author_payout = gross_revenue - platform_take

    return {
        "listing_count": len(listings),
        "total_installs": total_installs,
        "gross_revenue_usd": round(gross_revenue, 2),
        "platform_take_usd": round(platform_take, 2),
        "estimated_payout_usd": round(author_payout, 2),
        "take_rate_pct": take_rate_pct * 100,
        "note": (
            "Display only — no payment processing is wired. "
            "Revenue figures are estimates based on $1.00/install at a "
            f"{int(take_rate_pct * 100)}% platform take rate."
        ),
        "listings": [
            {
                "id": str(l.id),
                "name": l.name,
                "install_count": l.install_count,
                "estimated_payout_usd": round(l.install_count * REVENUE_PER_INSTALL_USD * (1 - take_rate_pct), 2),
            }
            for l in listings
        ],
    }
