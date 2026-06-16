from __future__ import annotations

import threading
from uuid import UUID

from agent_service.app.database.connection import get_connection
from agent_service.app.models.domain_event import DomainEventModel

# 进程内串行化「分配 sequence_no + 落库」这段临界区。
# barge-in 会让同一 session 出现并发写入的多个回合，若不加锁，
# next_sequence_no 的「读最大值」与 create 的「写入」之间存在竞态，
# 会分配出重复的 sequence_no，导致 SSE 按 id 去重时丢事件。
_SEQUENCE_LOCK = threading.Lock()


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

    def append(self, event: DomainEventModel) -> DomainEventModel:
        """原子地为事件分配下一个 sequence_no 并落库。

        所有产出 domain_event 的路径都应走这里（而非自行 next_sequence_no + create），
        以保证同一 session 的 sequence_no 在并发回合下仍严格单调、互不冲突。
        传入事件的 sequence_no 会被忽略并重新分配。
        """
        with _SEQUENCE_LOCK:
            sequence_no = self.next_sequence_no(event.session_id)
            stamped = event.model_copy(update={"sequence_no": sequence_no})
            return self.create(stamped)

    def list_by_session_id(self, session_id: UUID) -> list[DomainEventModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM domain_events").fetchall()
        conn.close()
        items = [DomainEventModel.model_validate_json(row[0]) for row in rows]
        return sorted(
            [item for item in items if item.session_id == session_id],
            key=lambda item: item.sequence_no,
        )

    def list_by_session_id_since(self, session_id: UUID, since: int = 0) -> list[DomainEventModel]:
        return [
            item
            for item in self.list_by_session_id(session_id)
            if item.sequence_no > since
        ]

    def list_by_run_id(self, run_id: UUID) -> list[DomainEventModel]:
        conn = get_connection()
        rows = conn.execute("SELECT payload FROM domain_events").fetchall()
        conn.close()
        items = [DomainEventModel.model_validate_json(row[0]) for row in rows]
        return sorted(
            [item for item in items if item.run_id == run_id],
            key=lambda item: item.sequence_no,
        )

    def next_sequence_no(self, session_id: UUID) -> int:
        items = self.list_by_session_id(session_id)
        if not items:
            return 1
        return items[-1].sequence_no + 1
