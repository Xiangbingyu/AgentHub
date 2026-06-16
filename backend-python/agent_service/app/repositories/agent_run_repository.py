from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from agent_service.app.database.connection import get_connection
from agent_service.app.models.agent_run import AgentRunModel


class AgentRunRepository:
    def create(self, agent_run: AgentRunModel) -> AgentRunModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO agent_runs (run_id, payload) VALUES (?, ?)",
            (str(agent_run.run_id), agent_run.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return agent_run

    def get_by_id(self, run_id: UUID) -> AgentRunModel | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM agent_runs WHERE run_id = ?",
            (str(run_id),),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return AgentRunModel.model_validate_json(row[0])

    def list_by_session_id(self, session_id: UUID) -> list[AgentRunModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM agent_runs").fetchall()
        conn.close()
        runs = [AgentRunModel.model_validate_json(row[0]) for row in rows]
        return [run for run in runs if run.session_id == session_id]

    def update(self, agent_run: AgentRunModel) -> AgentRunModel:
        agent_run.updated_at = datetime.now(timezone.utc)
        return self.create(agent_run)

    def update_status(self, run_id: UUID, status: str) -> AgentRunModel | None:
        agent_run = self.get_by_id(run_id)
        if agent_run is None:
            return None
        agent_run.status = status
        return self.update(agent_run)

    def create_run_id(self) -> UUID:
        return uuid4()
