from uuid import uuid4

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.services.domain_event_emitter import DomainEventEmitter


def test_emit_assigns_monotonic_sequence() -> None:
    bootstrap_memory_store()
    session_id = uuid4()
    session_workspace_id = uuid4()
    emitter = DomainEventEmitter()

    emitter.emit(
        session_id=session_id,
        session_workspace_id=session_workspace_id,
        event_type="run.started",
        event_scope="main_timeline",
        payload={"run_id": "r1"},
    )
    emitter.emit(
        session_id=session_id,
        session_workspace_id=session_workspace_id,
        event_type="run.completed",
        event_scope="main_timeline",
        payload={"run_id": "r1", "status": "completed"},
    )

    events = DomainEventRepository().list_by_session_id(session_id)

    assert [event.sequence_no for event in events] == [1, 2]
    assert events[0].event_type == "run.started"
    assert events[1].payload["status"] == "completed"
