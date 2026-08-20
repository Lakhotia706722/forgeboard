"""
MarketplaceListing ORM model — Phase 10a.

Listings are GLOBAL — not scoped to any workspace.
The config_payload is credential-free and workspace-agnostic.

Security invariant: config_payload must NEVER contain:
  - OAuth tokens, API keys, passwords, or secrets
  - workspace_id, agent_id, connector_id, or user_id values
  - Any data from a specific user's workspace

This is enforced at submission time by credential_scrubber.py (Phase 10c).
First-party listings are seeded directly via seed_marketplace.py and
are trusted — they were written by ForgeBoard engineers.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ListingStatus(str, PyEnum):
    DRAFT    = "draft"     # author editing, not visible publicly
    PENDING  = "pending"   # submitted, awaiting admin review
    APPROVED = "approved"  # visible in public catalog
    REJECTED = "rejected"  # rejected with reviewer note


class ListingType(str, PyEnum):
    AGENT     = "agent"      # installs an Agent into workspace
    CONNECTOR = "connector"  # installs a Connector config into workspace


class MarketplaceListing(Base):
    """
    A marketplace listing represents a reusable, shareable agent or connector
    template that any user can install into their workspace.

    config_payload structure (agent):
    {
      "name": "Calendar Summariser",
      "goal": "...",
      "trigger_type": "scheduled",
      "cron_schedule": "0 8 * * 1-5",
      "required_connector_types": ["google_calendar", "kv_store"],
      "requires_approval": false
    }

    config_payload structure (connector):
    {
      "name": "Google Calendar",
      "connector_type": "google_calendar",
      "config": {"calendar_id": "primary"}
    }

    Note: connector_map and connector credentials are intentionally absent.
    The install flow (Phase 10b) wires up the user's own connectors.
    """
    __tablename__ = "marketplace_listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # NULL = ForgeBoard first-party listing
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    author_name: Mapped[str] = mapped_column(String(255), nullable=False, default="ForgeBoard")

    listing_type: Mapped[ListingType] = mapped_column(
        SAEnum(ListingType, name="listingtype"),
        nullable=False,
        default=ListingType.AGENT,
    )
    status: Mapped[ListingStatus] = mapped_column(
        SAEnum(ListingStatus, name="listingstatus"),
        nullable=False,
        default=ListingStatus.DRAFT,
        index=True,
    )

    # Versioned, credential-free config payload stored as JSONB
    config_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0.0")

    preview_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Popularity counter — incremented on each install (Phase 10b)
    install_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    # Review fields
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    author: Mapped["User"] = relationship("User", foreign_keys=[author_user_id])  # type: ignore

    def __repr__(self) -> str:
        return f"<MarketplaceListing id={self.id} name={self.name!r} status={self.status}>"
