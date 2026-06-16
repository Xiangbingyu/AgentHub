from __future__ import annotations

from uuid import UUID

from agent_service.app.database.memory_store import STORE
from agent_service.app.models.agent import AgentModel
from agent_service.app.repositories.agent_repository import AgentRepository

# 内置 agent 使用固定 ID，保证跨进程/重启稳定，已持久化的 run 重启后仍能解析到 agent。
ORCHESTRATOR_AGENT_ID = UUID("00000000-0000-0000-0000-0000000000a1")
WORKER_AGENT_ID = UUID("00000000-0000-0000-0000-0000000000a2")


def seed_memory_store() -> None:
    if STORE.agents:
        return

    repository = AgentRepository()

    orchestrator = AgentModel(
        agent_id=ORCHESTRATOR_AGENT_ID,
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
    worker = AgentModel(
        agent_id=WORKER_AGENT_ID,
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

    # create 同时写 STORE 与 SQLite，使 agent 持久化。
    repository.create(orchestrator)
    repository.create(worker)
