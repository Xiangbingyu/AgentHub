from concurrent.futures import ThreadPoolExecutor
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


def test_append_assigns_unique_monotonic_sequence_under_concurrency() -> None:
    # barge-in 会让同一 session 出现并发回合并发写事件。append 必须保证
    # sequence_no 严格唯一且连续，否则 SSE 按 id 去重会丢事件、前端气泡消失。
    repository = DomainEventRepository()
    session_id = uuid4()
    session_workspace_id = uuid4()

    def emit_one(_: int) -> int:
        event = DomainEventModel(
            event_id=uuid4(),
            session_id=session_id,
            session_workspace_id=session_workspace_id,
            event_type="session.message.appended",
            event_scope="main_timeline",
            sequence_no=0,
            payload={"content": "x"},
        )
        return repository.append(event).sequence_no

    with ThreadPoolExecutor(max_workers=8) as pool:
        sequences = list(pool.map(emit_one, range(50)))

    assert len(set(sequences)) == 50, "并发分配出现了重复 sequence_no"
    assert sorted(sequences) == list(range(1, 51))
