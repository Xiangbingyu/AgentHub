from __future__ import annotations

from fastapi import APIRouter, Request

from gateway_service.app.client.agent_service_client import AgentServiceClient

router = APIRouter(tags=["write-proxy"])


@router.post("/agent-runs/{run_id}/input")
async def post_message(run_id: str, request: Request):
    body = await request.json()
    return AgentServiceClient().post_message(run_id, body)


@router.post("/sessions/{session_id}/messages")
async def post_session_message(session_id: str, request: Request):
    body = await request.json()
    return AgentServiceClient().post_session_message(session_id, body)


@router.post("/agent-runs")
async def create_agent_run(request: Request):
    body = await request.json()
    return AgentServiceClient().create_agent_run(body)


@router.post("/sessions")
async def create_session(request: Request):
    body = await request.json()
    return AgentServiceClient().create_session(body)


@router.post("/sessions/from-source")
async def create_session_from_source(request: Request):
    body = await request.json()
    return AgentServiceClient().create_session_from_source(body)


@router.post("/sessions/{session_id}/delete")
def delete_session(session_id: str):
    return AgentServiceClient().delete_session(session_id)


@router.post("/source-workspaces")
async def create_source_workspace(request: Request):
    body = await request.json()
    return AgentServiceClient().create_source_workspace(body)


@router.post("/session-workspaces")
async def create_session_workspace(request: Request):
    body = await request.json()
    return AgentServiceClient().create_session_workspace(body)


@router.post("/session-workspaces/derive")
async def derive_session_workspace(request: Request):
    body = await request.json()
    return AgentServiceClient().derive_session_workspace(body)
