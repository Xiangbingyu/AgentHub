from __future__ import annotations

from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.subtask import SubtaskModel


class SubtaskRepository:
    def create(self, subtask: SubtaskModel) -> SubtaskModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO subtasks (subtask_id, payload) VALUES (?, ?)",
            (str(subtask.subtask_id), subtask.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return subtask

    def get_by_id(self, subtask_id: UUID) -> SubtaskModel | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM subtasks WHERE subtask_id = ?",
            (str(subtask_id),),
        ).fetchone()
        conn.close()
        if row is None:
            return None
        return SubtaskModel.model_validate_json(row[0])

    def list_by_parent_run_id(self, parent_run_id: UUID) -> list[SubtaskModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM subtasks").fetchall()
        conn.close()
        subtasks = [SubtaskModel.model_validate_json(row[0]) for row in rows]
        return [subtask for subtask in subtasks if subtask.parent_run_id == parent_run_id]

    def update_status(self, subtask_id: UUID, status: str) -> SubtaskModel | None:
        subtask = self.get_by_id(subtask_id)
        if subtask is None:
            return None
        subtask.status = status
        return self.update(subtask)

    def update(self, subtask: SubtaskModel) -> SubtaskModel:
        return self.create(subtask)
