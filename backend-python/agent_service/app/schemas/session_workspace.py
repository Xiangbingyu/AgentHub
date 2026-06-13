from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class SessionWorkspaceCreateRequest(BaseModel):
    source_workspace_id: UUID
    name: str
    root_path: str


class SessionWorkspaceResponse(BaseModel):
    session_workspace_id: UUID
    source_workspace_id: UUID
    name: str
    root_path: str
    status: str
