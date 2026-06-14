from __future__ import annotations

from uuid import UUID, uuid4

from agent_service.app.models.domain_event import DomainEventModel
from agent_service.app.repositories.domain_event_repository import DomainEventRepository


class DomainEventEmitter:
    """集中产出 domain_event：自动分配 event_id 与按 session 单调递增的 sequence_no，

    避免 sequence_no 计算散落到各调用点。
    """

    def __init__(self, repository: DomainEventRepository | None = None) -> None:
        self._repository = repository or DomainEventRepository()

    def emit(
        self,
        *,
        session_id: UUID,
        session_workspace_id: UUID,
        event_type: str,
        event_scope: str,
        payload: dict[str, object],
        run_id: UUID | None = None,
        subtask_id: UUID | None = None,
    ) -> DomainEventModel:
        sequence_no = self._repository.next_sequence_no(session_id)
        event = DomainEventModel(
            event_id=uuid4(),
            session_id=session_id,
            session_workspace_id=session_workspace_id,
            run_id=run_id,
            subtask_id=subtask_id,
            event_type=event_type,
            event_scope=event_scope,
            payload=payload,
            sequence_no=sequence_no,
        )
        return self._repository.create(event)
