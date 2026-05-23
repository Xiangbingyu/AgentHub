from __future__ import annotations

from uuid import uuid4

from app.database.memory_store import STORE
from app.models.agent import AgentModel


def seed_memory_store() -> None:
    if STORE.agents:
        return

    orchestrator_agent_id = uuid4()
    worker_agent_id = uuid4()

    STORE.agents[orchestrator_agent_id] = AgentModel(
        agent_id=orchestrator_agent_id,
        agent_name="Orchestrator",
        agent_kind="orchestrator",
    )
    STORE.agents[worker_agent_id] = AgentModel(
        agent_id=worker_agent_id,
        agent_name="Worker",
        agent_kind="worker",
    )
