from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.input_event_repository import InputEventRepository
from app.schemas.agent_run_input import AgentRunInputRequest
from app.services.agent_run_input_service import AgentRunInputService


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def get_service() -> AgentRunInputService:
    return AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )


@router.post("/{run_id}/input")
def input_agent_run(run_id: UUID, payload: AgentRunInputRequest):
    try:
        return get_service().input(run_id=run_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
