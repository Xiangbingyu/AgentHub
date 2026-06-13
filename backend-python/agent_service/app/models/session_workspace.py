from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class SessionWorkspaceModel(BaseModel):
    session_workspace_id: UUID
    source_workspace_id: UUID
    name: str
    root_path: str
    status: str = "ready"
    origin_session_workspace_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
