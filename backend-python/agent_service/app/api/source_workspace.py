from __future__ import annotations

from fastapi import APIRouter

from agent_service.app.schemas.source_workspace import SourceWorkspaceCreateRequest
from agent_service.app.services.source_workspace_service import SourceWorkspaceService


router = APIRouter(prefix="/source-workspaces", tags=["source-workspaces"])


def get_service() -> SourceWorkspaceService:
    return SourceWorkspaceService()


@router.post("")
def create_source_workspace(payload: SourceWorkspaceCreateRequest):
    return get_service().create(payload)
