from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository
from agent_service.app.runtime.workspace.workspace_tree import list_tree_level

router = APIRouter(tags=["workspaces"])


@router.get("/source-workspaces")
def list_source_workspaces():
    return SourceWorkspaceRepository().list_all()


@router.get("/source-workspaces/{source_workspace_id}")
def get_source_workspace(source_workspace_id: UUID):
    source = SourceWorkspaceRepository().get_by_id(source_workspace_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source workspace not found")
    return source


@router.get("/source-workspaces/{source_workspace_id}/session-workspaces")
def list_session_workspaces(source_workspace_id: UUID):
    return SessionWorkspaceRepository().list_by_source_workspace_id(source_workspace_id)


@router.get("/source-workspaces/{source_workspace_id}/tree")
def get_source_workspace_tree(source_workspace_id: UUID, path: str = Query(default=".")):
    source = SourceWorkspaceRepository().get_by_id(source_workspace_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source workspace not found")
    try:
        return list_tree_level(source.root_path, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/session-workspaces/{session_workspace_id}")
def get_session_workspace(session_workspace_id: UUID):
    workspace = SessionWorkspaceRepository().get_by_id(session_workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="session workspace not found")
    return workspace
