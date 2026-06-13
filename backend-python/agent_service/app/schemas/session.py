from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class SessionCreateRequest(BaseModel):
    session_workspace_id: UUID
    title: str


class SessionResponse(BaseModel):
    session_id: UUID
    session_workspace_id: UUID
    title: str
    status: str
