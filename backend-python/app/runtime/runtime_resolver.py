from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository


@dataclass(slots=True)
class RuntimeContext:
    agent_run: AgentRunModel
    agent: AgentModel


class RuntimeResolver:
    def __init__(self, agent_run_repository: AgentRunRepository, agent_repository: AgentRepository) -> None:
        self.agent_run_repository = agent_run_repository
        self.agent_repository = agent_repository

    def resolve(self, run_id: UUID) -> RuntimeContext:
        agent_run = self.agent_run_repository.get_by_id(run_id)
        if agent_run is None:
            raise ValueError("run not found")

        agent = self.agent_repository.get_by_id(agent_run.agent_id)
        if agent is None:
            raise ValueError("agent not found")

        return RuntimeContext(agent_run=agent_run, agent=agent)
