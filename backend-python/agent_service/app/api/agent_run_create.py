from __future__ import annotations

from fastapi import APIRouter

from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.schemas.agent_run_create import AgentRunCreateRequest
from agent_service.app.services.agent_run_create_service import AgentRunCreateService


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def get_service() -> AgentRunCreateService:
    return AgentRunCreateService(
        agent_repository=AgentRepository(),
        agent_run_repository=AgentRunRepository(),
    )


@router.post("")
def create_agent_run(payload: AgentRunCreateRequest):
    return get_service().create_run(payload)
