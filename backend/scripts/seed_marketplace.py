"""
Seed the marketplace with ForgeBoard first-party listings.

Usage:
  cd backend
  python scripts/seed_marketplace.py

Idempotent — skips listings that already exist by name.

These listings are credential-free and workspace-agnostic.
They are seeded directly as APPROVED (bypassing the review queue)
because they are written by ForgeBoard engineers and are trusted.
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.marketplace import ListingStatus, ListingType, MarketplaceListing


FIRST_PARTY_LISTINGS = [
    {
        "name": "Calendar Summariser",
        "description": (
            "Every weekday morning, fetches today's Google Calendar events and "
            "summarises them into a concise plain-text agenda stored in the notes store. "
            "Requires Google Calendar and KV Store connectors."
        ),
        "category": "Productivity",
        "listing_type": ListingType.AGENT,
        "version": "1.0.0",
        "config_payload": {
            "name": "Calendar Summariser",
            "goal": (
                "Every weekday morning, fetch today's Google Calendar events, "
                "summarise them into a concise plain-text agenda (event name, time, location), "
                "and store the result in the notes store under the key 'todays_agenda'. "
                "If there are no events, write 'No events today' instead."
            ),
            "trigger_type": "scheduled",
            "cron_schedule": "0 8 * * 1-5",
            "required_connector_types": ["google_calendar", "kv_store"],
            "requires_approval": False,
        },
    },
    {
        "name": "Webhook-to-Email Notifier",
        "description": (
            "Listens for incoming webhooks and sends a summary email to an address "
            "stored in your notes store. Great for piping alerts from any HTTP source "
            "into your inbox. Requires HTTP Webhook, Gmail, and KV Store connectors."
        ),
        "category": "Notifications",
        "listing_type": ListingType.AGENT,
        "version": "1.0.0",
        "config_payload": {
            "name": "Webhook-to-Email Notifier",
            "goal": (
                "When triggered via webhook, read the incoming request body and send a "
                "summary email to the address stored in the notes store under key 'notify_email'. "
                "Use the subject line 'ForgeBoard Alert: New webhook event'. "
                "If 'notify_email' is not set, skip sending and log a warning in the notes store "
                "under key 'last_webhook_warning'."
            ),
            "trigger_type": "webhook",
            "cron_schedule": None,
            "required_connector_types": ["http_webhook", "gmail", "kv_store"],
            "requires_approval": False,
        },
    },
    {
        "name": "Daily Notes Digest",
        "description": (
            "Every evening, compiles all your notes store entries into a Markdown digest "
            "and emails it to you. A simple way to review what your agents saved during the day. "
            "Requires KV Store and Gmail connectors."
        ),
        "category": "Productivity",
        "listing_type": ListingType.AGENT,
        "version": "1.0.0",
        "config_payload": {
            "name": "Daily Notes Digest",
            "goal": (
                "Read all entries from the notes store and compose a Markdown-formatted "
                "daily digest listing each key and its value. "
                "Then send the digest as an email with the subject 'ForgeBoard Daily Notes Digest' "
                "to the address stored in the notes store under key 'digest_email'. "
                "If 'digest_email' is not set, just output the digest as plain text."
            ),
            "trigger_type": "scheduled",
            "cron_schedule": "0 18 * * *",
            "required_connector_types": ["kv_store", "gmail"],
            "requires_approval": False,
        },
    },
    {
        "name": "Calendar Event Creator",
        "description": (
            "Creates a Google Calendar event from a structured webhook payload. "
            "Useful for integrating external booking systems or form submissions. "
            "Requires HTTP Webhook and Google Calendar connectors."
        ),
        "category": "Calendar",
        "listing_type": ListingType.AGENT,
        "version": "1.0.0",
        "config_payload": {
            "name": "Calendar Event Creator",
            "goal": (
                "When triggered via webhook, parse the JSON body for fields: "
                "title, start_datetime (ISO 8601), end_datetime (ISO 8601), description, attendees (array of emails). "
                "Create a Google Calendar event with those details. "
                "Store the created event ID in the notes store under key 'last_created_event_id'. "
                "If required fields are missing, store an error message under key 'last_event_error'."
            ),
            "trigger_type": "webhook",
            "cron_schedule": None,
            "required_connector_types": ["http_webhook", "google_calendar", "kv_store"],
            "requires_approval": False,
        },
    },
    {
        "name": "Weekly Agenda Email",
        "description": (
            "Every Monday morning, fetches the week's Google Calendar events and "
            "emails a formatted weekly agenda. A good starting point for meeting-prep workflows. "
            "Requires Google Calendar and Gmail connectors."
        ),
        "category": "Calendar",
        "listing_type": ListingType.AGENT,
        "version": "1.0.0",
        "config_payload": {
            "name": "Weekly Agenda Email",
            "goal": (
                "Every Monday morning, fetch all Google Calendar events for the next 7 days. "
                "Format them as a Markdown weekly agenda grouped by day. "
                "Email the agenda to the address stored in the notes store under key 'agenda_email'. "
                "Subject line: 'Your Week Ahead — ForgeBoard'. "
                "If 'agenda_email' is not set in the notes store, skip sending."
            ),
            "trigger_type": "scheduled",
            "cron_schedule": "0 7 * * 1",
            "required_connector_types": ["google_calendar", "gmail", "kv_store"],
            "requires_approval": False,
        },
    },
]


async def seed():
    async with AsyncSessionLocal() as db:
        seeded = 0
        skipped = 0

        for tmpl in FIRST_PARTY_LISTINGS:
            existing = await db.execute(
                select(MarketplaceListing).where(
                    MarketplaceListing.name == tmpl["name"],
                    MarketplaceListing.author_user_id.is_(None),  # first-party
                )
            )
            if existing.scalar_one_or_none():
                print(f"  ↷ Skipping '{tmpl['name']}' (already exists)")
                skipped += 1
                continue

            listing = MarketplaceListing(
                name=tmpl["name"],
                description=tmpl["description"],
                category=tmpl["category"],
                listing_type=tmpl["listing_type"],
                author_user_id=None,
                author_name="ForgeBoard",
                config_payload=tmpl["config_payload"],
                version=tmpl.get("version", "1.0.0"),
                status=ListingStatus.APPROVED,  # first-party listings auto-approved
            )
            db.add(listing)
            print(f"  ✓ Seeded '{tmpl['name']}'")
            seeded += 1

        await db.commit()
        print(f"\nDone: {seeded} seeded, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(seed())
