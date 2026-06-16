from uuid import uuid4

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.database.memory_store import STORE
from agent_service.app.models.session import SessionModel
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.services.session_message_service import SessionMessageService


class _FakeInputService:
    def __init__(self):
        self.calls = []

    def input(self, run_id, payload):
        self.calls.append((run_id, payload))
        from agent_service.app.schemas.agent_run_input import AgentRunInputResponse

        return AgentRunInputResponse(run_id=run_id, status="accepted")


class _BlockingInputService:
    def __init__(self):
        self.calls = []
        self.entered = []
        self.started = None

    def input(self, run_id, payload):
        import time

        self.calls.append((run_id, payload))
        self.entered.append(run_id)
        if self.started is not None:
            self.started.set()
        if len(self.calls) == 1:
            time.sleep(10)
        from agent_service.app.schemas.agent_run_input import AgentRunInputResponse

        return AgentRunInputResponse(run_id=run_id, status="accepted")


def _create_session() -> SessionModel:
    return SessionRepository().create(
        SessionModel(
            session_id=uuid4(),
            session_workspace_id=uuid4(),
            title="msg session",
            status="active",
        )
    )


def test_send_creates_orchestrator_run_when_none_exists() -> None:
    bootstrap_memory_store()
    session = _create_session()
    fake_input = _FakeInputService()
    service = SessionMessageService(input_service=fake_input, async_runner=lambda job: job())

    response = service.send(session.session_id, content="hello")

    assert response.status == "accepted"
    # 为该 session 新建了一个 orchestrator run
    runs = AgentRunRepository().list_by_session_id(session.session_id)
    assert len(runs) == 1
    assert runs[0].agent_kind == "orchestrator"
    # input 被调用，且 payload 携带用户内容
    assert len(fake_input.calls) == 1
    run_id, payload = fake_input.calls[0]
    assert run_id == runs[0].run_id
    assert payload.payload["content"] == "hello"
    assert payload.type.value == "user_input"


def test_send_reuses_existing_run() -> None:
    bootstrap_memory_store()
    session = _create_session()
    fake_input = _FakeInputService()
    service = SessionMessageService(input_service=fake_input, async_runner=lambda job: job())

    service.send(session.session_id, content="first")
    service.send(session.session_id, content="second")

    runs = AgentRunRepository().list_by_session_id(session.session_id)
    assert len(runs) == 1  # 复用同一个 run，不重复创建


def test_concurrent_send_creates_fresh_run_when_previous_turn_is_active() -> None:
    import threading
    import time

    bootstrap_memory_store()
    session = _create_session()
    blocking_input = _BlockingInputService()
    service = SessionMessageService(input_service=blocking_input)
    started = threading.Event()
    blocking_input.started = started

    worker = threading.Thread(target=lambda: service.send(session.session_id, content="first"), daemon=True)
    worker.start()

    assert started.wait(timeout=2), "first send never entered input()"

    first_run_id = blocking_input.entered[0]
    handle = service.turn_coordinator.begin(first_run_id)

    response = service.send(session.session_id, content="second")

    service.turn_coordinator.end(first_run_id, handle.token)

    worker.join(timeout=0.1)

    assert response.status == "accepted"
    assert len(blocking_input.calls) >= 2
    first_run_id = blocking_input.calls[0][0]
    second_run_id = blocking_input.calls[1][0]
    assert first_run_id != second_run_id


def test_send_cancels_current_turn_before_background_dispatch(monkeypatch) -> None:
    bootstrap_memory_store()
    session = _create_session()
    fake_input = _FakeInputService()
    queued_jobs = []
    cancelled = []

    service = SessionMessageService(
        input_service=fake_input,
        async_runner=lambda job: queued_jobs.append(job),
    )

    class _FakeCoordinator:
        def cancel(self, run_id):
            cancelled.append(run_id)

    service.turn_coordinator = _FakeCoordinator()

    service.send(session.session_id, content="first")
    service.send(session.session_id, content="second")

    runs = AgentRunRepository().list_by_session_id(session.session_id)
    assert len(runs) == 1
    assert cancelled[-1] == runs[0].run_id


def test_send_raises_for_unknown_session() -> None:
    bootstrap_memory_store()
    service = SessionMessageService(
        input_service=_FakeInputService(), async_runner=lambda job: job()
    )

    try:
        service.send(uuid4(), content="x")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_orchestrator_agent_seeded() -> None:
    bootstrap_memory_store()
    kinds = {agent.agent_kind for agent in STORE.agents.values()}
    assert "orchestrator" in kinds
