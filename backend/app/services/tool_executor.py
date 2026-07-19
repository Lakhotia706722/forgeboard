"""
Tool execution layer — translates Claude's tool_use requests into real API calls
against the connected connectors.

Each connector type has its own executor function. The orchestration engine
calls execute_tool() with the tool name, inputs, and the connector's decrypted
credentials + config.

Design notes:
- All executors are async (httpx for HTTP).
- Errors are caught and returned as {"error": "..."} so the agent can see
  what went wrong and decide whether to retry.
- Google token refresh is handled transparently inside each Google executor.
"""
import base64
import email.mime.text
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.encryption import decrypt_json


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    connector_type: str,
    connector_config: dict[str, Any],
    encrypted_credentials: str | None,
) -> dict[str, Any]:
    """
    Route a tool call to the right executor based on connector type.
    Returns a dict that gets serialised and sent back to Claude as the tool result.
    """
    creds: dict = {}
    if encrypted_credentials:
        try:
            creds = decrypt_json(encrypted_credentials)
        except ValueError as e:
            return {"error": f"Credential decryption failed: {e}"}

    # Strip the namespace suffix added by agent_service (e.g. "kv_get__abc12345" -> "kv_get")
    base_name = tool_name.split("__")[0]

    try:
        if connector_type == "http_webhook":
            return await _exec_http(base_name, tool_input, connector_config, creds)

        elif connector_type == "google_calendar":
            return await _exec_calendar(base_name, tool_input, connector_config, creds)

        elif connector_type == "gmail":
            return await _exec_gmail(base_name, tool_input, connector_config, creds)

        elif connector_type == "kv_store":
            # KV store executor needs DB access — handled specially in orchestrator
            return {"_deferred": "kv", "base_name": base_name, "input": tool_input}

        else:
            return {"error": f"Unknown connector type: {connector_type}"}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# HTTP / Webhook executor
# ---------------------------------------------------------------------------

async def _exec_http(
    tool_name: str,
    inputs: dict[str, Any],
    config: dict[str, Any],
    creds: dict,
) -> dict[str, Any]:
    method = inputs.get("method", "GET").upper()
    url = inputs.get("url", config.get("webhook_url", ""))
    headers: dict[str, str] = inputs.get("headers") or {}
    body = inputs.get("body")

    if not url:
        return {"error": "No URL provided for HTTP request."}

    # Attach signing secret header if configured
    secret = creds.get("secret")
    secret_header = config.get("secret_header_name")
    if secret and secret_header:
        headers[secret_header] = secret

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        resp = await client.request(
            method=method,
            url=url,
            headers=headers,
            content=body.encode() if body else None,
        )

    result: dict[str, Any] = {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
    }
    try:
        result["body"] = resp.json()
    except Exception:
        result["body"] = resp.text[:4000]  # cap at 4k chars

    return result


# ---------------------------------------------------------------------------
# Google helpers — refresh access token
# ---------------------------------------------------------------------------

async def _refresh_google_token(creds: dict) -> dict:
    """Attempt to refresh the Google access token. Returns updated creds."""
    from app.core.config import settings

    async with httpx.AsyncClient() as client:
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
        return {**creds, **r.json()}
    return creds  # return original if refresh fails


def _auth_header(creds: dict) -> str:
    return f"Bearer {creds.get('access_token', '')}"


# ---------------------------------------------------------------------------
# Google Calendar executor
# ---------------------------------------------------------------------------

async def _exec_calendar(
    tool_name: str,
    inputs: dict[str, Any],
    config: dict[str, Any],
    creds: dict,
) -> dict[str, Any]:
    calendar_id = config.get("calendar_id", "primary")
    base_url = "https://www.googleapis.com/calendar/v3"

    # Try with current token; if 401, refresh once and retry
    for attempt in range(2):
        headers = {"Authorization": _auth_header(creds)}

        async with httpx.AsyncClient(timeout=30.0) as client:
            if tool_name == "calendar_list_events":
                now = datetime.now(timezone.utc).isoformat()
                params: dict[str, Any] = {
                    "maxResults": inputs.get("max_results", 10),
                    "timeMin": inputs.get("time_min", now),
                    "singleEvents": True,
                    "orderBy": "startTime",
                }
                if inputs.get("time_max"):
                    params["timeMax"] = inputs["time_max"]
                if inputs.get("query"):
                    params["q"] = inputs["query"]

                r = await client.get(
                    f"{base_url}/calendars/{calendar_id}/events",
                    headers=headers,
                    params=params,
                )

            elif tool_name == "calendar_create_event":
                body = {
                    "summary": inputs.get("summary", ""),
                    "description": inputs.get("description", ""),
                    "start": {"dateTime": inputs["start_datetime"], "timeZone": "UTC"},
                    "end": {"dateTime": inputs["end_datetime"], "timeZone": "UTC"},
                }
                if inputs.get("attendees"):
                    body["attendees"] = [{"email": e} for e in inputs["attendees"]]

                r = await client.post(
                    f"{base_url}/calendars/{calendar_id}/events",
                    headers={**headers, "Content-Type": "application/json"},
                    content=json.dumps(body),
                )
            else:
                return {"error": f"Unknown calendar tool: {tool_name}"}

        if r.status_code == 401 and attempt == 0:
            creds = await _refresh_google_token(creds)
            continue

        if r.status_code >= 400:
            return {"error": f"Google Calendar API error {r.status_code}: {r.text[:500]}"}

        return r.json()

    return {"error": "Google Calendar authentication failed after token refresh."}


# ---------------------------------------------------------------------------
# Gmail executor
# ---------------------------------------------------------------------------

async def _exec_gmail(
    tool_name: str,
    inputs: dict[str, Any],
    config: dict[str, Any],
    creds: dict,
) -> dict[str, Any]:
    if tool_name != "gmail_send":
        return {"error": f"Unknown Gmail tool: {tool_name}"}

    to = inputs.get("to", "")
    subject = inputs.get("subject", "")
    body = inputs.get("body", "")
    cc = inputs.get("cc")
    sender_name = config.get("sender_name", "ForgeBoard Agent")

    if not to or not subject or not body:
        return {"error": "gmail_send requires 'to', 'subject', and 'body'."}

    # Build RFC 2822 message
    msg = email.mime.text.MIMEText(body, "plain")
    msg["to"] = to
    msg["subject"] = subject
    msg["from"] = f"{sender_name} <me>"
    if cc:
        msg["cc"] = cc

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

    for attempt in range(2):
        headers = {
            "Authorization": _auth_header(creds),
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers=headers,
                content=json.dumps({"raw": raw}),
            )

        if r.status_code == 401 and attempt == 0:
            creds = await _refresh_google_token(creds)
            continue

        if r.status_code >= 400:
            return {"error": f"Gmail API error {r.status_code}: {r.text[:500]}"}

        return {"sent": True, "message_id": r.json().get("id")}

    return {"error": "Gmail authentication failed after token refresh."}
