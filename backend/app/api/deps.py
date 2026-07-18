"""
FastAPI dependency factories for use across all endpoint modules.
"""
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

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
