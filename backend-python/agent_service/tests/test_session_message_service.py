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
