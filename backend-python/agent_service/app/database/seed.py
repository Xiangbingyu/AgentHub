from __future__ import annotations

from uuid import uuid4

from agent_service.app.database.memory_store import STORE
from agent_service.app.models.agent import AgentModel


def seed_memory_store() -> None:
    if STORE.agents:
        return

    orchestrator_agent_id = uuid4()
    worker_agent_id = uuid4()

    STORE.agents[orchestrator_agent_id] = AgentModel(
        agent_id=orchestrator_agent_id,
        agent_name="Orchestrator",
        agent_kind="orchestrator",
        tool_config={
            "tools": [
                {"name": "plan_tool"},
                {"name": "delegate_tool"},
                {"name": "bash_tool"},
            ],
            "auto_tool_choice": True,
        },
    )
    STORE.agents[worker_agent_id] = AgentModel(
        agent_id=worker_agent_id,
        agent_name="Worker",
        agent_kind="worker",
        tool_config={
            "tools": [
                {"name": "code_tool"},
                {"name": "bash_tool"},
            ],
            "auto_tool_choice": True,
        },
    )
