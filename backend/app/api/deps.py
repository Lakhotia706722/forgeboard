"""
FastAPI dependency factories for use across all endpoint modules.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User, Workspace
from app.services.auth_service import get_current_user

bearer_scheme = HTTPBearer()


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated User from the Bearer token."""
    return await get_current_user(credentials.credentials, db)


async def current_workspace(
    user: Annotated[User, Depends(current_user)],
) -> Workspace:
    """
    Return the active workspace for the current user.
    For MVP there is exactly one workspace per user.
    """
    if not user.workspaces:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workspace found for this user.",
        )
    return user.workspaces[0]


# Convenient type aliases for injection
CurrentUser = Annotated[User, Depends(current_user)]
CurrentWorkspace = Annotated[Workspace, Depends(current_workspace)]
DB = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Twilio webhook signature validation
# ---------------------------------------------------------------------------

async def validate_twilio_signature(request: Request) -> None:
    """
    Verify the X-Twilio-Signature header on inbound Twilio webhook requests.

    Twilio signs every webhook POST with HMAC-SHA1 using your auth token.
    If the signature is missing or invalid we return 403.

    Docs: https://www.twilio.com/docs/usage/webhooks/webhooks-security

    Note: This validation requires TWILIO_AUTH_TOKEN and TWILIO_WEBHOOK_BASE_URL
    to be configured. In development with ngrok, ensure TWILIO_WEBHOOK_BASE_URL
    exactly matches the URL Twilio is posting to (including the path).
    """
    if not settings.TWILIO_AUTH_TOKEN:
        # Auth token not configured — skip validation (dev/test only)
        return

    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        # twilio package not installed — skip (shouldn't happen in production)
        return

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    signature = request.headers.get("X-Twilio-Signature", "")

    # Reconstruct the full URL Twilio posted to
    url = str(request.url)
    if settings.TWILIO_WEBHOOK_BASE_URL:
        # Replace the host portion with the configured public URL so the
        # signature matches even when behind a reverse proxy / ngrok tunnel.
        from urllib.parse import urlparse, urlunparse
        parsed_request = urlparse(url)
        parsed_base = urlparse(settings.TWILIO_WEBHOOK_BASE_URL)
        url = urlunparse(parsed_request._replace(
            scheme=parsed_base.scheme,
            netloc=parsed_base.netloc,
        ))

    # Twilio includes POST params in the signature for application/x-www-form-urlencoded
    form_params: dict[str, str] = {}
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        form_params = dict(form_data)

    if not validator.validate(url, form_params, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Twilio signature.",
        )


TwilioWebhook = Annotated[None, Depends(validate_twilio_signature)]
