"""create compliance tables: consent_records, dnc_entries, calling_hours_rules

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # consent_records
    # ------------------------------------------------------------------
    op.create_table(
        "consent_records",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone_number", sa.String(30), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("consent_method", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("consent_text", sa.Text(), nullable=True),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_consent_records_workspace_id", "consent_records", ["workspace_id"])
    op.create_index("ix_consent_records_phone_number", "consent_records", ["phone_number"])
    # Composite index for the primary lookup pattern
    op.create_index(
        "ix_consent_records_workspace_phone",
        "consent_records",
        ["workspace_id", "phone_number"],
    )

    # ------------------------------------------------------------------
    # dnc_entries
    # ------------------------------------------------------------------
    op.create_table(
        "dnc_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("phone_number", sa.String(30), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_dnc_entries_workspace_id", "dnc_entries", ["workspace_id"])
    op.create_index("ix_dnc_entries_phone_number", "dnc_entries", ["phone_number"])
    # Unique constraint: one entry per (workspace, number)
    op.create_unique_constraint(
        "uq_dnc_entries_workspace_phone",
        "dnc_entries",
        ["workspace_id", "phone_number"],
    )

    # ------------------------------------------------------------------
    # calling_hours_rules
    # ------------------------------------------------------------------
    op.create_table(
        "calling_hours_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("region_code", sa.String(10), nullable=False, server_default="*"),
        sa.Column(
            "days_of_week",
            sa.String(40),
            nullable=False,
            server_default="mon,tue,wed,thu,fri",
        ),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="America/New_York"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_calling_hours_rules_workspace_id", "calling_hours_rules", ["workspace_id"]
    )

    # ------------------------------------------------------------------
    # Add skip_compliance_checks + escalation_number to voice_agents
    # ------------------------------------------------------------------
    op.add_column(
        "voice_agents",
        sa.Column(
            "skip_compliance_checks",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "voice_agents",
        sa.Column("escalation_number", sa.String(30), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("voice_agents", "escalation_number")
    op.drop_column("voice_agents", "skip_compliance_checks")
    op.drop_table("calling_hours_rules")
    op.drop_table("dnc_entries")
    op.drop_table("consent_records")
