"""
Connector business logic: CRUD, health checks, OAuth token storage.
"""
import json
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_json, encrypt_json
from app.models.connector import Connector, ConnectorStatus, ConnectorType
from app.models.kv_store import KvEntry
from app.schemas.connector import (
    ConnectorOut,
    GmailCreate,
    GoogleCalendarCreate,
    HttpWebhookCreate,
    KvStoreCreate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_out(connector: Connector) -> ConnectorOut:
    return ConnectorOut.model_validate(connector)


async def _get_or_404(connector_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession) -> Connector:
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.workspace_id == workspace_id,
        )
    )
    conn = result.scalar_one_or_none()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connector not found.")
    return conn


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_connectors(workspace_id: uuid.UUID, db: AsyncSession) -> list[ConnectorOut]:
    result = await db.execute(
        select(Connector).where(Connector.workspace_id == workspace_id)
    )
    return [_to_out(c) for c in result.scalars().all()]


async def get_connector(
    connector_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> ConnectorOut:
    return _to_out(await _get_or_404(connector_id, workspace_id, db))


async def delete_connector(
    connector_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> None:
    conn = await _get_or_404(connector_id, workspace_id, db)
    await db.delete(conn)


# ---------------------------------------------------------------------------
# Create — one factory per connector type
# ---------------------------------------------------------------------------

async def create_http_webhook(
    workspace_id: uuid.UUID, data: HttpWebhookCreate, db: AsyncSession
) -> ConnectorOut:
    config = {}
    if data.webhook_url:
        config["webhook_url"] = data.webhook_url
    if data.secret_header_name:
        config["secret_header_name"] = data.secret_header_name

    creds: dict = {}
    if data.secret:
        creds["secret"] = data.secret

    conn = Connector(
        workspace_id=workspace_id,
        name=data.name,
        connector_type=ConnectorType.HTTP_WEBHOOK,
        status=ConnectorStatus.CONNECTED,  # no auth needed
        config_json=json.dumps(config) if config else None,
        encrypted_credentials=encrypt_json(creds) if creds else None,
    )
    db.add(conn)
    await db.flush()
    return _to_out(conn)


async def create_kv_store(
    workspace_id: uuid.UUID, data: KvStoreCreate, db: AsyncSession
) -> ConnectorOut:
    # Check: only one KV store per workspace for MVP
    existing = await db.execute(
        select(Connector).where(
            Connector.workspace_id == workspace_id,
            Connector.connector_type == ConnectorType.KV_STORE,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A key-value store already exists for this workspace.",
        )

    conn = Connector(
        workspace_id=workspace_id,
        name=data.name,
        connector_type=ConnectorType.KV_STORE,
        status=ConnectorStatus.CONNECTED,  # internal — always connected
    )
    db.add(conn)
    await db.flush()
    return _to_out(conn)


async def create_google_calendar(
    workspace_id: uuid.UUID, data: GoogleCalendarCreate, db: AsyncSession
) -> ConnectorOut:
    """
    Creates the connector record in PENDING_AUTH state.
    The OAuth flow (initiate_google_oauth / handle_google_callback) will
    update status to CONNECTED once tokens are obtained.
    """
    config = {"calendar_id": data.calendar_id}
    conn = Connector(
        workspace_id=workspace_id,
        name=data.name,
        connector_type=ConnectorType.GOOGLE_CALENDAR,
        status=ConnectorStatus.PENDING_AUTH,
        config_json=json.dumps(config),
    )
    db.add(conn)
    await db.flush()
    return _to_out(conn)


async def create_gmail(
    workspace_id: uuid.UUID, data: GmailCreate, db: AsyncSession
) -> ConnectorOut:
    config: dict = {}
    if data.sender_name:
        config["sender_name"] = data.sender_name

    conn = Connector(
        workspace_id=workspace_id,
        name=data.name,
        connector_type=ConnectorType.GMAIL,
        status=ConnectorStatus.PENDING_AUTH,
        config_json=json.dumps(config) if config else None,
    )
    db.add(conn)
    await db.flush()
    return _to_out(conn)


# ---------------------------------------------------------------------------
# Google OAuth flow
# ---------------------------------------------------------------------------

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "openid",
    "email",
    "profile",
]

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def build_google_oauth_url(connector_id: uuid.UUID, client_id: str, redirect_uri: str) -> str:
    import urllib.parse

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        # Encode connector_id in state so we know which connector to update on callback
        "state": str(connector_id),
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


async def handle_google_callback(
    code: str,
    connector_id: uuid.UUID,
    workspace_id: uuid.UUID,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    db: AsyncSession,
) -> ConnectorOut:
    """Exchange auth code for tokens and save encrypted to the connector."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Google token exchange failed: {resp.text}",
        )

    tokens = resp.json()
    conn = await _get_or_404(connector_id, workspace_id, db)
    conn.encrypted_credentials = encrypt_json(tokens)
    conn.status = ConnectorStatus.CONNECTED
    conn.last_checked_at = _now()
    conn.last_error = None
    await db.flush()
    return _to_out(conn)


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

async def health_check_connector(
    connector_id: uuid.UUID, workspace_id: uuid.UUID, db: AsyncSession
) -> ConnectorOut:
    conn = await _get_or_404(connector_id, workspace_id, db)
    now = _now()

    if conn.connector_type == ConnectorType.KV_STORE:
        conn.status = ConnectorStatus.CONNECTED
        conn.last_error = None

    elif conn.connector_type == ConnectorType.HTTP_WEBHOOK:
        # For HTTP connector: attempt a GET to the webhook URL if configured
        config = json.loads(conn.config_json) if conn.config_json else {}
        url = config.get("webhook_url")
        if url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(url)
                if r.status_code < 500:
                    conn.status = ConnectorStatus.CONNECTED
                    conn.last_error = None
                else:
                    conn.status = ConnectorStatus.ERROR
                    conn.last_error = f"Webhook returned HTTP {r.status_code}"
            except Exception as e:
                conn.status = ConnectorStatus.ERROR
                conn.last_error = str(e)
        else:
            conn.status = ConnectorStatus.CONNECTED  # no URL yet — treat as configured
            conn.last_error = None

    elif conn.connector_type in (ConnectorType.GOOGLE_CALENDAR, ConnectorType.GMAIL):
        if not conn.encrypted_credentials:
            conn.status = ConnectorStatus.PENDING_AUTH
            conn.last_error = "No OAuth tokens — complete the Google OAuth flow."
        else:
            try:
                creds = decrypt_json(conn.encrypted_credentials)
                # Try refreshing the access token to confirm validity
                async with httpx.AsyncClient() as client:
                    from app.core.config import settings
                    r = await client.post(
                        "https://oauth2.googleapis.com/token",
                        data={
                            "client_id": settings.GOOGLE_CLIENT_ID,
                            "client_secret": settings.GOOGLE_CLIENT_SECRET,
                            "refresh_token": creds.get("refresh_token", ""),
                            "grant_type": "refresh_token",
                        },
                    )
                if r.status_code == 200:
                    # Save the refreshed access token
                    updated = {**creds, **r.json()}
                    conn.encrypted_credentials = encrypt_json(updated)
                    conn.status = ConnectorStatus.CONNECTED
                    conn.last_error = None
                else:
                    conn.status = ConnectorStatus.ERROR
                    conn.last_error = "Token refresh failed — re-authenticate."
            except Exception as e:
                conn.status = ConnectorStatus.ERROR
                conn.last_error = str(e)

    conn.last_checked_at = now
    await db.flush()
    return _to_out(conn)


# ---------------------------------------------------------------------------
# KV Store operations
# ---------------------------------------------------------------------------

async def kv_set(
    workspace_id: uuid.UUID, key: str, value: str, db: AsyncSession
) -> KvEntry:
    result = await db.execute(
        select(KvEntry).where(
            KvEntry.workspace_id == workspace_id,
            KvEntry.key == key,
        )
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry.value = value
        entry.updated_at = _now()
    else:
        entry = KvEntry(workspace_id=workspace_id, key=key, value=value)
        db.add(entry)
    await db.flush()
    return entry


async def kv_get(
    workspace_id: uuid.UUID, key: str, db: AsyncSession
) -> KvEntry | None:
    result = await db.execute(
        select(KvEntry).where(
            KvEntry.workspace_id == workspace_id,
            KvEntry.key == key,
        )
    )
    return result.scalar_one_or_none()


async def kv_delete(workspace_id: uuid.UUID, key: str, db: AsyncSession) -> bool:
    entry = await kv_get(workspace_id, key, db)
    if entry:
        await db.delete(entry)
        return True
    return False


async def kv_list(workspace_id: uuid.UUID, db: AsyncSession) -> list[KvEntry]:
    result = await db.execute(
        select(KvEntry).where(KvEntry.workspace_id == workspace_id)
    )
    return list(result.scalars().all())
