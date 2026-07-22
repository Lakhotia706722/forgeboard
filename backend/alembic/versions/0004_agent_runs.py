"""create agent_runs table

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "running", "success", "failed", "cancelled",
                name="runstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("trigger_source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("celery_task_id", sa.String(255), nullable=True),
        sa.Column("trace_json", sa.Text(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_agent_runs_agent_id", "agent_runs", ["agent_id"])
    op.create_index("ix_agent_runs_workspace_id", "agent_runs", ["workspace_id"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.execute("DROP TYPE runstatus")
