"""
Pydantic schemas for bulk agent actions — Phase 9e.
"""
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class BulkStatusUpdate(BaseModel):
    """Pause or resume multiple agents at once."""
    agent_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    status: Literal["paused", "live", "draft", "testing"] = Field(
        description="Target status to move all selected agents to."
    )


class BulkDelete(BaseModel):
    """Delete multiple agents at once."""
    agent_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)


class BulkCloneRequest(BaseModel):
    """Clone multiple agents from one workspace to another (agency view)."""
    agent_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    source_workspace_id: uuid.UUID
    dest_workspace_id: uuid.UUID


class BulkActionResult(BaseModel):
    """Summary returned after any bulk action."""
    succeeded: list[uuid.UUID]
    failed: list[dict]  # {"agent_id": str, "reason": str}
    total: int
    success_count: int
    failure_count: int
