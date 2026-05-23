from __future__ import annotations

from uuid import UUID

from app.database.memory_store import STORE
from app.models.subtask import SubtaskModel


class SubtaskRepository:
    def create(self, subtask: SubtaskModel) -> SubtaskModel:
        STORE.subtasks[subtask.subtask_id] = subtask
        return subtask

    def get_by_id(self, subtask_id: UUID) -> SubtaskModel | None:
        return STORE.subtasks.get(subtask_id)

    def list_by_parent_run_id(self, parent_run_id: UUID) -> list[SubtaskModel]:
        return [subtask for subtask in STORE.subtasks.values() if subtask.parent_run_id == parent_run_id]

    def update_status(self, subtask_id: UUID, status: str) -> SubtaskModel | None:
        subtask = self.get_by_id(subtask_id)
        if subtask is None:
            return None
        subtask.status = status
        STORE.subtasks[subtask_id] = subtask
        return subtask

    def update(self, subtask: SubtaskModel) -> SubtaskModel:
        STORE.subtasks[subtask.subtask_id] = subtask
        return subtask
