from __future__ import annotations

import httpx
from fastapi import APIRouter

from gateway_service.app.client.agent_service_client import AgentServiceClient

router = APIRouter(prefix="/workspace-page", tags=["workspace-page"])


@router.get("/{source_workspace_id}")
def get_workspace_page(source_workspace_id: str):
    client = AgentServiceClient()
    source = client.get_source_workspace(source_workspace_id)
    session_workspaces = client.list_session_workspaces(source_workspace_id)

    tree: list[dict] = []
    try:
        tree = client.get_workspace_tree(source_workspace_id, path=".")
    except httpx.HTTPStatusError as exc:
        # root_path 可能在当前环境不存在——降级为空树，不阻断整页
        if exc.response.status_code not in (400, 404):
            raise

    return {
        "source_workspace": source,
        "session_workspaces": session_workspaces,
        "tree": tree,
    }
