from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from agent_service.app.repositories.agent_run_repository import AgentRunRepository

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get("/{run_id}")
def get_agent_run(run_id: UUID):
    run = AgentRunRepository().get_by_id(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return run
