from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class SessionWorkspaceCreateRequest(BaseModel):
    source_workspace_id: UUID
    name: str
    root_path: str


class SessionWorkspaceDeriveRequest(BaseModel):
    source_workspace_id: UUID
    name: str | None = None


class SessionWorkspaceResponse(BaseModel):
    session_workspace_id: UUID
    source_workspace_id: UUID
    name: str
    root_path: str
    status: str
    origin_session_workspace_id: UUID | None = None
