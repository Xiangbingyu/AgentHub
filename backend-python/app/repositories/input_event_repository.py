from __future__ import annotations

from uuid import UUID

from app.database.memory_store import STORE
from app.models.input_event import InputEventModel


class InputEventRepository:
    def create(self, input_event: InputEventModel) -> InputEventModel:
        STORE.input_events[input_event.input_id] = input_event
        return input_event

    def get_by_idempotency_key(self, run_id: UUID, idempotency_key: str) -> InputEventModel | None:
        for input_event in STORE.input_events.values():
            if input_event.run_id == run_id and input_event.idempotency_key == idempotency_key:
                return input_event
        return None

    def list_by_run_id(self, run_id: UUID) -> list[InputEventModel]:
        return [event for event in STORE.input_events.values() if event.run_id == run_id]
