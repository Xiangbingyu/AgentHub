from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.database.memory_store import STORE
from agent_service.app.models.agent import AgentModel


class AgentRepository:
    """Agent 以 SQLite 为持久层、STORE 为内存读缓存。

    内置 agent 由 seed 写入并固定 ID（见 seed.py），重启后 bootstrap 会先
    从库 warm 回 STORE，使已持久化的 run 仍能解析到对应 agent。
    """

    def create(self, agent: AgentModel) -> AgentModel:
        STORE.agents[agent.agent_id] = agent
        self._persist(agent)
        return agent

    def get_by_id(self, agent_id: UUID) -> AgentModel | None:
        cached = STORE.agents.get(agent_id)
        if cached is not None:
            return cached

        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM agents WHERE agent_id = ?",
            (str(agent_id),),
        ).fetchone()
        conn.close()
        if row is None:
            return None

        agent = AgentModel.model_validate_json(row[0])
        STORE.agents[agent.agent_id] = agent
        return agent

    def list_all(self) -> list[AgentModel]:
        return list(STORE.agents.values())

    def update(self, agent: AgentModel) -> AgentModel:
        agent.updated_at = datetime.now(timezone.utc)
        STORE.agents[agent.agent_id] = agent
        self._persist(agent)
        return agent

    def warm_cache(self) -> None:
        """启动时把持久化的 agents 载入 STORE。"""
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM agents").fetchall()
        conn.close()
        for row in rows:
            agent = AgentModel.model_validate_json(row[0])
            STORE.agents[agent.agent_id] = agent

    def _persist(self, agent: AgentModel) -> None:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO agents (agent_id, payload) VALUES (?, ?)",
            (str(agent.agent_id), agent.model_dump_json()),
        )
        conn.commit()
        conn.close()
