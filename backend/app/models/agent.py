"""
Agent ORM model.

An Agent is the core unit of ForgeBoard — it has a goal, a set of connectors,
a trigger, and a status that maps to the Kanban board lanes.

agent_config_json: the compiled system prompt + tool config used by the
orchestration engine in Phase 4. Built by agent_service.build_agent_config().
"""
import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AgentStatus(str, PyEnum):
    DRAFT = "draft"
    TESTING = "testing"
    LIVE = "live"
    PAUSED = "paused"
    NEEDS_REVIEW = "needs_review"


class TriggerType(str, PyEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    WEBHOOK = "webhook"


class Agent(Base):
    __tablename__ = "agents"

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

    # Free-text goal description — used as the agent's primary prompt
    goal: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus, name="agentstatus", values_callable=lambda x: [e.value for e in x]),
        default=AgentStatus.DRAFT,
        nullable=False,
        index=True,
    )
    trigger_type: Mapped[TriggerType] = mapped_column(
        SAEnum(TriggerType, name="triggertype", values_callable=lambda x: [e.value for e in x]),
        default=TriggerType.MANUAL,
        nullable=False,
    )
    # Cron expression for scheduled triggers — e.g. "0 9 * * 1-5"
    cron_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Webhook secret for incoming webhook triggers (stored encrypted in Phase 4)
    webhook_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Compiled agent config — system prompt + tool definitions
    # Built by agent_service.build_agent_config() and stored so Phase 4 can
    # execute without re-building it every run.
    agent_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Governance: require manual approval before tool calls execute (Phase 6)
    requires_approval: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Soft counters — updated by the orchestration engine in Phase 4
    total_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    # Relationships
    connector_links: Mapped[list["AgentConnector"]] = relationship(
        "AgentConnector", back_populates="agent", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Agent id={self.id} name={self.name!r} status={self.status}>"


class AgentConnector(Base):
    """Junction table: which connectors an agent has access to."""
    __tablename__ = "agent_connectors"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connectors.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="connector_links")
    connector: Mapped["Connector"] = relationship("Connector")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<AgentConnector agent={self.agent_id} connector={self.connector_id}>"
