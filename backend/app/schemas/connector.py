"""
Pydantic schemas for connector endpoints.
Credentials are never returned to the client — only status + config.
"""
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.connector import ConnectorStatus, ConnectorType


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class ConnectorOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    connector_type: ConnectorType
    status: ConnectorStatus
    config_json: dict[str, Any] | None = None
    last_checked_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: Any) -> None:
        # Parse config_json string → dict if stored as string in DB
        import json
        if isinstance(self.config_json, str):
            try:
                object.__setattr__(self, "config_json", json.loads(self.config_json))
            except (json.JSONDecodeError, TypeError):
                object.__setattr__(self, "config_json", None)


# ---------------------------------------------------------------------------
# HTTP / Webhook connector
# ---------------------------------------------------------------------------

class HttpWebhookConfig(BaseModel):
    """Public (non-secret) config stored in config_json."""
    webhook_url: str | None = None
    secret_header_name: str | None = None  # e.g. "X-Hub-Signature"

class HttpWebhookCreate(BaseModel):
    name: str = Field(default="HTTP / Webhook", max_length=255)
    webhook_url: str | None = None
    # Optional secret for signing outbound requests — stored encrypted
    secret: str | None = None
    secret_header_name: str | None = None


# ---------------------------------------------------------------------------
# Google Calendar connector
# ---------------------------------------------------------------------------

class GoogleCalendarConfig(BaseModel):
    calendar_id: str | None = "primary"

class GoogleCalendarCreate(BaseModel):
    name: str = Field(default="Google Calendar", max_length=255)
    calendar_id: str = "primary"
    # OAuth tokens injected server-side after callback — not provided by client directly


# ---------------------------------------------------------------------------
# Gmail connector
# ---------------------------------------------------------------------------

class GmailConfig(BaseModel):
    sender_name: str | None = None

class GmailCreate(BaseModel):
    name: str = Field(default="Gmail", max_length=255)
    sender_name: str | None = None


# ---------------------------------------------------------------------------
# Key-Value notes store (internal, no external auth)
# ---------------------------------------------------------------------------

class KvStoreCreate(BaseModel):
    name: str = Field(default="Notes Store", max_length=255)


# ---------------------------------------------------------------------------
# Health check response
# ---------------------------------------------------------------------------

class HealthCheckResult(BaseModel):
    connector_id: uuid.UUID
    status: ConnectorStatus
    message: str
    checked_at: datetime


# ---------------------------------------------------------------------------
# KV store operation schemas (used by agents + UI)
# ---------------------------------------------------------------------------

class KvSetRequest(BaseModel):
    key: str = Field(max_length=255)
    value: str

class KvGetResponse(BaseModel):
    key: str
    value: str | None

class KvListResponse(BaseModel):
    entries: list[dict[str, str]]
