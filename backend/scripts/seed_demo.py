"""
Seed script: creates a demo user + workspace + 3 pre-built agent templates
so a new user sees something useful immediately.

Usage:
  cd backend
  python scripts/seed_demo.py

Requires DATABASE_URL and FERNET_KEY to be set (via .env or environment).

⚠  Idempotent — safe to run multiple times (skips if demo user already exists).
"""
import asyncio
import json
import sys
import os

# Ensure app is importable when run from backend/
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.agent import Agent, AgentConnector, AgentStatus, TriggerType
from app.models.connector import Connector, ConnectorStatus, ConnectorType
from app.models.user import User, Workspace
from app.services.agent_service import build_agent_config


DEMO_EMAIL = "demo@forgeboard.dev"
DEMO_PASSWORD = "Demo1234!"
DEMO_NAME = "Demo User"

# ---------------------------------------------------------------------------
# Demo agent templates
# ---------------------------------------------------------------------------

TEMPLATES = [
    {
        "name": "Calendar Summariser",
        "goal": (
            "Every weekday morning, fetch today's Google Calendar events, "
            "summarise them into a concise plain-text agenda (event name, time, location), "
            "and store the result in the notes store under the key 'todays_agenda'. "
            "If there are no events, write 'No events today' instead."
        ),
        "trigger_type": TriggerType.SCHEDULED,
        "cron_schedule": "0 8 * * 1-5",
        "connector_types": [ConnectorType.GOOGLE_CALENDAR, ConnectorType.KV_STORE],
        "status": AgentStatus.DRAFT,
    },
    {
        "name": "Webhook-to-Email Notifier",
        "goal": (
            "When triggered via webhook, read the incoming request body and send a "
            "summary email to the address stored in the notes store under key 'notify_email'. "
            "Use the subject line 'ForgeBoard Alert: New webhook event'. "
            "If 'notify_email' is not set, skip sending and log a warning in the notes store "
            "under key 'last_webhook_warning'."
        ),
        "trigger_type": TriggerType.WEBHOOK,
        "cron_schedule": None,
        "connector_types": [ConnectorType.HTTP_WEBHOOK, ConnectorType.GMAIL, ConnectorType.KV_STORE],
        "status": AgentStatus.DRAFT,
    },
    {
        "name": "Daily Notes Digest",
        "goal": (
            "Read all entries from the notes store and compose a Markdown-formatted "
            "daily digest listing each key and its value. "
            "Then send the digest as an email with the subject 'ForgeBoard Daily Notes Digest' "
            "to the address stored in the notes store under key 'digest_email'. "
            "If 'digest_email' is not set, just output the digest as plain text."
        ),
        "trigger_type": TriggerType.SCHEDULED,
        "cron_schedule": "0 18 * * *",
        "connector_types": [ConnectorType.KV_STORE, ConnectorType.GMAIL],
        "status": AgentStatus.DRAFT,
    },
]


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Check if already seeded ───────────────────────────────────────────
        existing = await db.execute(select(User).where(User.email == DEMO_EMAIL))
        if existing.scalar_one_or_none():
            print(f"✓ Demo user '{DEMO_EMAIL}' already exists — skipping seed.")
            return

        print(f"Creating demo user: {DEMO_EMAIL}")

        # ── Create user + workspace ───────────────────────────────────────────
        user = User(
            email=DEMO_EMAIL,
            full_name=DEMO_NAME,
            hashed_password=hash_password(DEMO_PASSWORD),
        )
        db.add(user)
        await db.flush()

        workspace = Workspace(
            name="Demo Workspace",
            slug="demo-workspace",
            owner_id=user.id,
        )
        db.add(workspace)
        await db.flush()

        # ── Create one connector per needed type ──────────────────────────────
        connector_map: dict[ConnectorType, Connector] = {}
        connector_defs = [
            (ConnectorType.KV_STORE,      "Notes Store",       ConnectorStatus.CONNECTED),
            (ConnectorType.HTTP_WEBHOOK,  "HTTP / Webhook",    ConnectorStatus.CONNECTED),
            (ConnectorType.GOOGLE_CALENDAR,"Google Calendar",  ConnectorStatus.PENDING_AUTH),
            (ConnectorType.GMAIL,         "Gmail",             ConnectorStatus.PENDING_AUTH),
        ]
        for ctype, name, status in connector_defs:
            conn = Connector(
                workspace_id=workspace.id,
                name=name,
                connector_type=ctype,
                status=status,
                config_json=json.dumps({"calendar_id": "primary"}) if ctype == ConnectorType.GOOGLE_CALENDAR else None,
            )
            db.add(conn)
            await db.flush()
            connector_map[ctype] = conn

        # ── Create demo agents ────────────────────────────────────────────────
        for tmpl in TEMPLATES:
            connectors = [
                connector_map[ct]
                for ct in tmpl["connector_types"]
                if ct in connector_map
            ]

            agent = Agent(
                workspace_id=workspace.id,
                name=tmpl["name"],
                goal=tmpl["goal"],
                trigger_type=tmpl["trigger_type"],
                cron_schedule=tmpl.get("cron_schedule"),
                status=tmpl["status"],
            )
            db.add(agent)
            await db.flush()

            for conn in connectors:
                db.add(AgentConnector(agent_id=agent.id, connector_id=conn.id))

            config = build_agent_config(agent, connectors)
            agent.agent_config_json = config.model_dump_json()

            print(f"  ✓ Created agent: {agent.name}")

        await db.commit()
        print(f"\nSeed complete!")
        print(f"  Email:    {DEMO_EMAIL}")
        print(f"  Password: {DEMO_PASSWORD}")
        print(f"  Login at: http://localhost:5173/login")


if __name__ == "__main__":
    asyncio.run(seed())
