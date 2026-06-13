from __future__ import annotations

from fastapi import APIRouter

from agent_service.app.schemas.session_workspace import SessionWorkspaceCreateRequest
from agent_service.app.services.session_workspace_service import SessionWorkspaceService


router = APIRouter(prefix="/session-workspaces", tags=["session-workspaces"])


def get_service() -> SessionWorkspaceService:
    return SessionWorkspaceService()


@router.post("")
def create_session_workspace(payload: SessionWorkspaceCreateRequest):
    return get_service().create(payload)
