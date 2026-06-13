from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from agent_service.app.database.memory_store import STORE
from agent_service.app.models.agent import AgentModel


class AgentRepository:
    def create(self, agent: AgentModel) -> AgentModel:
        STORE.agents[agent.agent_id] = agent
        return agent

    def get_by_id(self, agent_id: UUID) -> AgentModel | None:
        return STORE.agents.get(agent_id)

    def update(self, agent: AgentModel) -> AgentModel:
        agent.updated_at = datetime.now(timezone.utc)
        STORE.agents[agent.agent_id] = agent
        return agent
