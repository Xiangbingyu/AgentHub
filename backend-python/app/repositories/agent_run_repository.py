from __future__ import annotations

from datetime import datetime, timezone

from uuid import UUID, uuid4

from app.database.memory_store import STORE
from app.models.agent_run import AgentRunModel


class AgentRunRepository:
    def create(self, agent_run: AgentRunModel) -> AgentRunModel:
        STORE.agent_runs[agent_run.run_id] = agent_run
        return agent_run

    def get_by_id(self, run_id: UUID) -> AgentRunModel | None:
        return STORE.agent_runs.get(run_id)

    def update(self, agent_run: AgentRunModel) -> AgentRunModel:
        agent_run.updated_at = datetime.now(timezone.utc)
        STORE.agent_runs[agent_run.run_id] = agent_run
        return agent_run

    def update_status(self, run_id: UUID, status: str) -> AgentRunModel | None:
        agent_run = self.get_by_id(run_id)
        if agent_run is None:
            return None
        agent_run.status = status
        STORE.agent_runs[run_id] = agent_run
        return agent_run

    def create_run_id(self) -> UUID:
        return uuid4()
