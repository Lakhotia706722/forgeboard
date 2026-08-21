"""
PlatformAuditLog — platform-wide event log for SOC 2 / Phase 11a.

Covers all meaningful actions outside agent tool calls (which remain in
the existing audit_log table). This table is append-only — entries must
never be updated or deleted except by the retention cleanup job.

Event type naming convention:  "{resource}.{action}"
  member.invited           workspace_member  invited_user_id
  member.accepted          workspace_member  user_id
  member.role_changed      workspace_member  user_id
  member.removed           workspace_member  user_id
  connector.created        connector         connector_id
  connector.deleted        connector         connector_id
  connector.health_checked connector         connector_id
  marketplace.submitted    marketplace_listing  listing_id
  marketplace.approved     marketplace_listing  listing_id
  marketplace.rejected     marketplace_listing  listing_id
  marketplace.installed    marketplace_listing  listing_id
  compliance.bypass_used   voice_agent       voice_agent_id
  settings.spend_cap_changed    workspace    workspace_id
  settings.branding_updated     workspace    workspace_id
  settings.workspace_updated    workspace    workspace_id
  vault.key_rotated         workspace        workspace_id   (Phase 11b)
  sso.configured            workspace        workspace_id   (Phase 11c)
  sso.login                 user             user_id        (Phase 11c)
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PlatformAuditLog(Base):
    __tablename__ = "platform_audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Who — nullable for system-initiated actions
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Denormalized so the entry is readable even if the user is later deleted
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Where — nullable for global platform events
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # What
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # State snapshots — what changed
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Security context
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<PlatformAuditLog event={self.event_type} "
            f"actor={self.actor_email} ws={self.workspace_id}>"
        )
