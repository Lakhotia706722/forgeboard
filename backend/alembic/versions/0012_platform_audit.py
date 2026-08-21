"""create platform_audit_log table and add audit retention to workspaces

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-28

The existing audit_log table covers agent tool calls (Phase 6).
This migration adds platform_audit_log — a workspace-scoped event log covering
all other meaningful platform actions:

  - Workspace membership changes (invite, accept, role change, remove)
  - Connector connect/disconnect/health-check
  - Marketplace submissions, approvals, rejections, installs
  - Voice agent compliance flag usage (skip_compliance_checks)
  - Billing/settings changes (spend cap, branding, workspace settings)
  - Secrets vault key rotation events (Phase 11b)
  - SSO configuration changes (Phase 11c)

Schema:
  actor_user_id   — who performed the action (nullable: system actions)
  actor_email     — denormalized for readability even if user is later deleted
  workspace_id    — workspace context (nullable for global platform events)
  event_type      — machine-readable action name (e.g. "member.invited")
  resource_type   — what was acted on (e.g. "workspace_member", "connector")
  resource_id     — UUID of the affected resource
  before_state    — JSONB snapshot before the change (nullable)
  after_state     — JSONB snapshot after the change (nullable)
  ip_address      — client IP for security auditing (nullable)
  user_agent      — browser/client for security auditing (nullable)
  created_at      — immutable timestamp

Retention:
  audit_retention_days column added to workspaces (default 365 = 1 year).
  A cleanup job (Phase 11a scheduled task) purges entries older than this.
  Enterprise customers typically need 3–7 years; default is 1 year.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # platform_audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "platform_audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "actor_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Denormalized — survives user deletion
        sa.Column("actor_email", sa.String(255), nullable=True),
        sa.Column("actor_name", sa.String(255), nullable=True),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # e.g. "member.invited", "connector.deleted", "marketplace.listing.approved"
        sa.Column("event_type", sa.String(100), nullable=False),
        # e.g. "workspace_member", "connector", "marketplace_listing"
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("before_state", JSONB, nullable=True),
        sa.Column("after_state", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),   # supports IPv6
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_platform_audit_workspace_id",
        "platform_audit_log",
        ["workspace_id"],
    )
    op.create_index(
        "ix_platform_audit_actor_user_id",
        "platform_audit_log",
        ["actor_user_id"],
    )
    op.create_index(
        "ix_platform_audit_event_type",
        "platform_audit_log",
        ["event_type"],
    )
    op.create_index(
        "ix_platform_audit_created_at",
        "platform_audit_log",
        ["created_at"],
    )
    op.create_index(
        "ix_platform_audit_resource",
        "platform_audit_log",
        ["resource_type", "resource_id"],
    )

    # ------------------------------------------------------------------
    # Retention period on workspaces
    # ------------------------------------------------------------------
    op.add_column(
        "workspaces",
        sa.Column(
            "audit_retention_days",
            sa.Integer(),
            nullable=False,
            server_default="365",  # 1 year default
        ),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "audit_retention_days")
    op.drop_table("platform_audit_log")
