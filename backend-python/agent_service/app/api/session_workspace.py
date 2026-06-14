from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent_service.app.schemas.session_workspace import (
    SessionWorkspaceCreateRequest,
    SessionWorkspaceDeriveRequest,
)
from agent_service.app.services.session_workspace_service import SessionWorkspaceService

router = APIRouter(prefix="/session-workspaces", tags=["session-workspaces"])


def get_service() -> SessionWorkspaceService:
    return SessionWorkspaceService()


@router.post("")
def create_session_workspace(payload: SessionWorkspaceCreateRequest):
    return get_service().create(payload)


@router.post("/derive")
def derive_session_workspace(payload: SessionWorkspaceDeriveRequest):
    try:
        return get_service().derive_from_source(payload.source_workspace_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
