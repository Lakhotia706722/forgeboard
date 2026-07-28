"""
Compliance models for Phase 8b.

Three tables:
  consent_records     — per-callee opt-in tracking
  dnc_entries         — workspace do-not-call list
  calling_hours_rules — per-region allowed calling windows

These are checked by voice_service.initiate_outbound_call() before every
outbound call.  Inbound calls are not gated — callers initiate those.

⚠ This is engineering scaffolding.  The data structures here do not
constitute legal compliance.  Review with qualified legal counsel before
placing outbound AI calls to real people.
"""
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Consent records
# ---------------------------------------------------------------------------

class ConsentRecord(Base):
    """
    Records that a specific phone number has given (or revoked) consent to
    receive AI-initiated outbound calls from this workspace.

    A consent record is considered active when:
      consent_given = True  AND  revoked_at IS NULL
    """
    __tablename__ = "consent_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # E.164 format, e.g. +15551234567
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    consent_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # How consent was captured: "web_form" | "sms_reply" | "ivr" | "manual"
    consent_method: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")

    # The exact consent wording shown / read to the callee at time of capture.
    # Storing verbatim is important for defensibility.
    consent_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<ConsentRecord phone={self.phone_number} "
            f"given={self.consent_given} revoked={self.revoked_at is not None}>"
        )


# ---------------------------------------------------------------------------
# Do-not-call entries
# ---------------------------------------------------------------------------

class DncEntry(Base):
    """
    A phone number that must never receive an outbound call from this workspace.

    Duplicate (workspace_id, phone_number) pairs are rejected at the service
    layer (upsert-style) so callers don't have to deduplicate.
    """
    __tablename__ = "dnc_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # Where this entry came from: "manual" | "callee_request" | "national_registry_import"
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    def __repr__(self) -> str:
        return f"<DncEntry phone={self.phone_number} workspace={self.workspace_id}>"


# ---------------------------------------------------------------------------
# Calling-hours rules
# ---------------------------------------------------------------------------

class CallingHoursRule(Base):
    """
    Defines allowed outbound calling windows for a workspace, per region.

    Stored as local times + IANA timezone string.  Enforcement converts
    the current UTC time to the rule's timezone before comparing.

    region_code examples:
      "*"       — applies to all calls (wildcard / default)
      "US"      — US national default
      "US-CA"   — California-specific override
      "GB"      — United Kingdom

    Evaluation order at enforcement time:
      1. Most-specific match (US-CA beats US beats *)
      2. If no rule matches, the call is ALLOWED (open by default).
         Set a restrictive "*" rule to flip this to deny-by-default.

    days_of_week: comma-separated lowercase abbreviations.
      e.g. "mon,tue,wed,thu,fri"  or  "mon,tue,wed,thu,fri,sat"
    """
    __tablename__ = "calling_hours_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Region code — "*" for wildcard
    region_code: Mapped[str] = mapped_column(String(10), nullable=False, default="*")

    # Comma-separated day abbreviations: "mon,tue,wed,thu,fri"
    days_of_week: Mapped[str] = mapped_column(
        String(40), nullable=False, default="mon,tue,wed,thu,fri"
    )

    # Local start / end times stored as TIME (no timezone) — zone in timezone field
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    # IANA timezone string, e.g. "America/Los_Angeles", "America/New_York", "Europe/London"
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="America/New_York")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<CallingHoursRule region={self.region_code} "
            f"tz={self.timezone} {self.start_time}-{self.end_time}>"
        )
