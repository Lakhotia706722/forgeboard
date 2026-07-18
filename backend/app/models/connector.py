"""
Connector ORM model.

Credentials are stored encrypted (Fernet) — see app.core.encryption.
⚠ MVP: upgrade to HashiCorp Vault / AWS Secrets Manager before production.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConnectorType(str, PyEnum):
    HTTP_WEBHOOK = "http_webhook"
    GOOGLE_CALENDAR = "google_calendar"
    GMAIL = "gmail"
    KV_STORE = "kv_store"


class ConnectorStatus(str, PyEnum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    PENDING_AUTH = "pending_auth"


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[ConnectorType] = mapped_column(
        SAEnum(ConnectorType, name="connectortype"), nullable=False
    )
    status: Mapped[ConnectorStatus] = mapped_column(
        SAEnum(ConnectorStatus, name="connectorstatus"),
        default=ConnectorStatus.DISCONNECTED,
        nullable=False,
    )
    # Encrypted JSON blob — contains OAuth tokens or API keys depending on type
    # Format varies per connector type (see ConnectorCredentials in schemas)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Human-readable config (non-secret): e.g. webhook URL, calendar ID
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Last time the health check ran
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Last error message if status == ERROR
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<Connector id={self.id} type={self.connector_type} status={self.status}>"
