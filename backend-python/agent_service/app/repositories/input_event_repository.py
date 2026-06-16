from __future__ import annotations

from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.input_event import InputEventModel


class InputEventRepository:
    def create(self, input_event: InputEventModel) -> InputEventModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO input_events (input_id, payload) VALUES (?, ?)",
            (str(input_event.input_id), input_event.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return input_event

    def get_by_idempotency_key(self, run_id: UUID, idempotency_key: str) -> InputEventModel | None:
        for input_event in self.list_by_run_id(run_id):
            if input_event.run_id == run_id and input_event.idempotency_key == idempotency_key:
                return input_event
        return None

    def list_by_run_id(self, run_id: UUID) -> list[InputEventModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM input_events").fetchall()
        conn.close()
        events = [InputEventModel.model_validate_json(row[0]) for row in rows]
        return [event for event in events if event.run_id == run_id]
