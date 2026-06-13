from __future__ import annotations

from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.domain_event import DomainEventModel


class DomainEventRepository:
    def create(self, event: DomainEventModel) -> DomainEventModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO domain_events (event_id, payload) VALUES (?, ?)",
            (str(event.event_id), event.model_dump_json()),
        )
        conn.commit()
        conn.close()
        return event

    def list_by_session_id(self, session_id: UUID) -> list[DomainEventModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM domain_events").fetchall()
        conn.close()
        items = [DomainEventModel.model_validate_json(row[0]) for row in rows]
        return sorted(
            [item for item in items if item.session_id == session_id],
            key=lambda item: item.sequence_no,
        )

    def next_sequence_no(self, session_id: UUID) -> int:
        items = self.list_by_session_id(session_id)
        if not items:
            return 1
        return items[-1].sequence_no + 1
