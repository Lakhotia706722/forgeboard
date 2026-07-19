"""
AgentRun ORM model.

One record per execution of an agent. Stores the full trace so Phase 5
can display run history and Phase 6 can export the audit log.
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


class RunStatus(str, PyEnum):
    PENDING = "pending"       # queued, not yet picked up by worker
    RUNNING = "running"       # Celery task is executing
    SUCCESS = "success"       # completed normally
    FAILED = "failed"         # exhausted retries or fatal error
    CANCELLED = "cancelled"   # manually stopped


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, name="runstatus"),
        default=RunStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Trigger that initiated this run: "manual", "scheduled", "webhook"
    trigger_source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)

    # Celery task ID for status polling
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Full execution trace — JSON array of trace events (see TraceEvent schema)
    trace_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Final output produced by the agent
    output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Error message if status == FAILED
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Token usage — used for cost estimation
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Cost in USD cents (estimated: $3/Mtok input, $15/Mtok output for Claude Sonnet)
    cost_usd_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent")  # type: ignore[name-defined]

    def __repr__(self) -> str:
        return f"<AgentRun id={self.id} agent={self.agent_id} status={self.status}>"
