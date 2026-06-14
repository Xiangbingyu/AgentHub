from uuid import uuid4

from agent_service.app.models.domain_event import DomainEventModel
from agent_service.app.repositories.domain_event_repository import DomainEventRepository


def test_domain_event_repository_lists_session_events_in_sequence() -> None:
    repository = DomainEventRepository()
    session_id = uuid4()
    session_workspace_id = uuid4()
    first = DomainEventModel(
        event_id=uuid4(),
        session_id=session_id,
        session_workspace_id=session_workspace_id,
        event_type="session.message.appended",
        event_scope="main_timeline",
        sequence_no=1,
        payload={"content": "hello"},
    )
    second = DomainEventModel(
        event_id=uuid4(),
        session_id=session_id,
        session_workspace_id=session_workspace_id,
        event_type="plan.updated",
        event_scope="main_timeline",
        sequence_no=2,
        payload={"summary": "updated"},
    )

    repository.create(first)
    repository.create(second)
    items = repository.list_by_session_id(session_id)

    assert [item.sequence_no for item in items] == [1, 2]


def test_domain_event_repository_list_since_filters_by_sequence_no() -> None:
    repository = DomainEventRepository()
    session_id = uuid4()
    session_workspace_id = uuid4()
    first = DomainEventModel(
        event_id=uuid4(),
        session_id=session_id,
        session_workspace_id=session_workspace_id,
        event_type="run.started",
        event_scope="main_timeline",
        sequence_no=1,
        payload={"run_id": "r1"},
    )
    second = DomainEventModel(
        event_id=uuid4(),
        session_id=session_id,
        session_workspace_id=session_workspace_id,
        event_type="run.completed",
        event_scope="main_timeline",
        sequence_no=2,
        payload={"run_id": "r1", "status": "completed"},
    )

    repository.create(first)
    repository.create(second)
    items = repository.list_by_session_id_since(session_id, since=1)

    assert [item.sequence_no for item in items] == [2]
