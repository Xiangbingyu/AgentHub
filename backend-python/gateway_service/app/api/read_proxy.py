from __future__ import annotations

from fastapi import APIRouter, Query

from gateway_service.app.client.agent_service_client import AgentServiceClient

router = APIRouter(tags=["read-proxy"])


@router.get("/sessions")
def list_sessions():
    return AgentServiceClient().list_sessions()


@router.get("/source-workspaces")
def list_source_workspaces():
    return AgentServiceClient().list_source_workspaces()


@router.get("/source-workspaces/{source_workspace_id}/tree")
def get_workspace_tree(source_workspace_id: str, path: str = Query(default=".")):
    return AgentServiceClient().get_workspace_tree(source_workspace_id, path=path)


@router.get("/session-workspaces/{session_workspace_id}/tree")
def get_session_workspace_tree(session_workspace_id: str, path: str = Query(default=".")):
    return AgentServiceClient().get_session_workspace_tree(session_workspace_id, path=path)
