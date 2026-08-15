"""
Connector endpoints:
  GET    /connectors                     — list workspace connectors   [all roles]
  GET    /connectors/{id}               — get one                     [all roles]
  DELETE /connectors/{id}               — disconnect / remove         [admin, owner]
  POST   /connectors/http               — create HTTP/webhook         [admin, owner]
  POST   /connectors/kv                 — create KV store             [admin, owner]
  POST   /connectors/google-calendar    — create Google Calendar      [admin, owner]
  POST   /connectors/gmail              — create Gmail                [admin, owner]
  GET    /connectors/oauth/google/init/{connector_id}   — redirect to Google OAuth
  GET    /connectors/oauth/google/callback              — OAuth callback
  POST   /connectors/{id}/health-check  — run health check            [admin, owner]
  GET    /connectors/{id}/kv            — list KV entries             [all roles]
  PUT    /connectors/{id}/kv/{key}      — set KV entry                [builder, admin, owner]
  GET    /connectors/{id}/kv/{key}      — get KV entry                [all roles]
  DELETE /connectors/{id}/kv/{key}      — delete KV entry             [builder, admin, owner]
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.api.deps import CurrentUser, CurrentWorkspace, DB, require_role
from app.core.config import settings
from app.models.connector import ConnectorType
from app.schemas.connector import (
    ConnectorOut,
    GmailCreate,
    GoogleCalendarCreate,
    HealthCheckResult,
    HttpWebhookCreate,
    KvGetResponse,
    KvListResponse,
    KvSetRequest,
    KvStoreCreate,
)
from app.services import connector_service
from datetime import datetime, timezone

router = APIRouter()

_ADMIN_UP   = require_role("owner", "admin")
_BUILDER_UP = require_role("owner", "admin", "builder")


# ---------------------------------------------------------------------------
# List / Get / Delete
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ConnectorOut])
async def list_connectors(workspace: CurrentWorkspace, db: DB):
    return await connector_service.list_connectors(workspace.id, db)


@router.get("/{connector_id}", response_model=ConnectorOut)
async def get_connector(connector_id: uuid.UUID, workspace: CurrentWorkspace, db: DB):
    return await connector_service.get_connector(connector_id, workspace.id, db)


@router.delete("/{connector_id}", status_code=204)
async def delete_connector(
    connector_id: uuid.UUID,
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    await connector_service.delete_connector(connector_id, workspace.id, db)


# ---------------------------------------------------------------------------
# Create connectors
# ---------------------------------------------------------------------------

@router.post("/http", response_model=ConnectorOut, status_code=201)
async def create_http_webhook(
    body: HttpWebhookCreate,
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    return await connector_service.create_http_webhook(workspace.id, body, db)


@router.post("/kv", response_model=ConnectorOut, status_code=201)
async def create_kv_store(
    body: KvStoreCreate,
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    return await connector_service.create_kv_store(workspace.id, body, db)


@router.post("/google-calendar", response_model=ConnectorOut, status_code=201)
async def create_google_calendar(
    body: GoogleCalendarCreate,
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    return await connector_service.create_google_calendar(workspace.id, body, db)


@router.post("/gmail", response_model=ConnectorOut, status_code=201)
async def create_gmail(
    body: GmailCreate,
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    return await connector_service.create_gmail(workspace.id, body, db)


# ---------------------------------------------------------------------------
# Google OAuth flow
# ---------------------------------------------------------------------------

@router.get("/oauth/google/init/{connector_id}")
async def google_oauth_init(
    connector_id: uuid.UUID,
    workspace: CurrentWorkspace,
    db: DB,
):
    """
    Build the Google OAuth authorization URL and redirect the user to it.
    connector_id is encoded in the OAuth state param.
    """
    # Verify the connector exists and belongs to this workspace
    await connector_service.get_connector(connector_id, workspace.id, db)

    url = connector_service.build_google_oauth_url(
        connector_id=connector_id,
        client_id=settings.GOOGLE_CLIENT_ID,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )
    return RedirectResponse(url)


@router.get("/oauth/google/callback")
async def google_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),  # connector_id encoded here
    workspace: CurrentWorkspace = None,  # type: ignore[assignment]
    db: DB = None,  # type: ignore[assignment]
    # Note: this endpoint is hit by Google's redirect so there's no auth header.
    # We use state (connector_id) to identify the connector.
    # Production hardening: add CSRF protection via state token verification.
):
    """
    Google OAuth callback — exchanges auth code for tokens, saves to connector.
    Redirects to the connectors page on success.
    """
    from sqlalchemy import select
    from app.models.connector import Connector
    from app.core.database import AsyncSessionLocal

    connector_id = uuid.UUID(state)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Connector).where(Connector.id == connector_id)
        )
        conn = result.scalar_one_or_none()
        if not conn:
            return RedirectResponse("/connectors?error=connector_not_found")

        await connector_service.handle_google_callback(
            code=code,
            connector_id=connector_id,
            workspace_id=conn.workspace_id,
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            redirect_uri=settings.GOOGLE_REDIRECT_URI,
            db=session,
        )
        await session.commit()

    return RedirectResponse("/connectors?connected=google")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@router.post("/{connector_id}/health-check", response_model=ConnectorOut)
async def health_check(
    connector_id: uuid.UUID,
    _: Annotated[None, _ADMIN_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    return await connector_service.health_check_connector(connector_id, workspace.id, db)


# ---------------------------------------------------------------------------
# KV Store operations
# ---------------------------------------------------------------------------

@router.get("/{connector_id}/kv", response_model=KvListResponse)
async def kv_list(connector_id: uuid.UUID, workspace: CurrentWorkspace, db: DB):
    """List all key-value entries for this workspace's KV store."""
    conn = await connector_service.get_connector(connector_id, workspace.id, db)
    if conn.connector_type != ConnectorType.KV_STORE:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=400, detail="Connector is not a KV store.")
    entries = await connector_service.kv_list(workspace.id, db)
    return KvListResponse(entries=[{"key": e.key, "value": e.value} for e in entries])


@router.put("/{connector_id}/kv/{key}", response_model=KvGetResponse)
async def kv_set(
    connector_id: uuid.UUID,
    key: str,
    body: KvSetRequest,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    entry = await connector_service.kv_set(workspace.id, key, body.value, db)
    return KvGetResponse(key=entry.key, value=entry.value)


@router.get("/{connector_id}/kv/{key}", response_model=KvGetResponse)
async def kv_get(connector_id: uuid.UUID, key: str, workspace: CurrentWorkspace, db: DB):
    entry = await connector_service.kv_get(workspace.id, key, db)
    return KvGetResponse(key=key, value=entry.value if entry else None)


@router.delete("/{connector_id}/kv/{key}", status_code=204)
async def kv_delete(
    connector_id: uuid.UUID,
    key: str,
    _: Annotated[None, _BUILDER_UP],
    workspace: CurrentWorkspace,
    db: DB,
):
    await connector_service.kv_delete(workspace.id, key, db)
