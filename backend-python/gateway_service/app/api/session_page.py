from __future__ import annotations

import httpx
from fastapi import APIRouter

from gateway_service.app.client.agent_service_client import AgentServiceClient

router = APIRouter(prefix="/session-page", tags=["session-page"])

# event_scope → 前端视图块的归属
_SCOPE_KEYS = ("main_timeline", "subtask_thread", "workspace_panel")


@router.get("/{session_id}")
def get_session_page(session_id: str):
    client = AgentServiceClient()
    session = client.get_session(session_id)
    events = client.list_session_events(session_id, since=0)

    projected: dict[str, list[dict]] = {key: [] for key in _SCOPE_KEYS}
    for event in events:
        scope = event.get("event_scope")
        if scope in projected:
            projected[scope].append(event)

    session_workspace = None
    session_workspace_id = session.get("session_workspace_id") if session else None
    if session_workspace_id:
        try:
            session_workspace = client.get_session_workspace(session_workspace_id)
        except httpx.HTTPStatusError as exc:
            # workspace 可能尚未落库（旧 session 引用未 seed 的 workspace）——降级为 None
            if exc.response.status_code != 404:
                raise

    return {
        "session": session,
        "session_workspace": session_workspace,
        **projected,
    }
