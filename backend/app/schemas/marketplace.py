"""
Pydantic schemas for marketplace endpoints — Phase 10.
"""
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.marketplace import ListingStatus, ListingType


# ---------------------------------------------------------------------------
# Catalog (public read)
# ---------------------------------------------------------------------------

class ListingOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    category: str
    author_name: str
    listing_type: ListingType
    status: ListingStatus
    version: str
    preview_image_url: str | None
    install_count: int
    created_at: datetime
    updated_at: datetime
    # config_payload intentionally excluded from list view — fetched per listing

    model_config = {"from_attributes": True}


class ListingDetail(ListingOut):
    """Full listing including the config payload — returned on single GET."""
    config_payload: dict[str, Any]


class ListingSearchParams(BaseModel):
    q: str | None = None
    category: str | None = None
    listing_type: ListingType | None = None
    sort: Literal["popular", "recent"] = "popular"
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Submission (Phase 10c)
# ---------------------------------------------------------------------------

class ListingSubmit(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=20, max_length=4000)
    category: str = Field(min_length=1, max_length=100)
    listing_type: ListingType = ListingType.AGENT
    config_payload: dict[str, Any] = Field(
        description=(
            "Credential-free, workspace-agnostic config. "
            "Must not contain OAuth tokens, API keys, workspace IDs, or agent IDs. "
            "Will be scanned before entering the review queue."
        )
    )
    preview_image_url: str | None = None


# ---------------------------------------------------------------------------
# Admin review (Phase 10c)
# ---------------------------------------------------------------------------

class ReviewAction(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = Field(
        default=None,
        description="Required when action=reject. Shown to the submitter.",
    )


# ---------------------------------------------------------------------------
# Install result (Phase 10b)
# ---------------------------------------------------------------------------

class InstallResult(BaseModel):
    listing_id: uuid.UUID
    listing_name: str
    installed_type: ListingType
    # For agent installs
    agent_id: uuid.UUID | None = None
    # For connector installs
    connector_id: uuid.UUID | None = None
    workspace_id: uuid.UUID
