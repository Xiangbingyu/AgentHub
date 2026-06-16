from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent_service.app.schemas.source_workspace import SourceWorkspaceCreateRequest
from agent_service.app.services.source_workspace_service import SourceWorkspaceService

router = APIRouter(prefix="/source-workspaces", tags=["source-workspaces"])


def get_service() -> SourceWorkspaceService:
    return SourceWorkspaceService()


@router.post("")
def create_source_workspace(payload: SourceWorkspaceCreateRequest):
    try:
        return get_service().create(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
