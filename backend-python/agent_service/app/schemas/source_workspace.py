from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class SourceWorkspaceCreateRequest(BaseModel):
    name: str
    root_path: str


class SourceWorkspaceResponse(BaseModel):
    source_workspace_id: UUID
    name: str
    root_path: str
    status: str
