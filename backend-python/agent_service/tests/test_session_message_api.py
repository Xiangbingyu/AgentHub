from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.main import app
from agent_service.app.models.session import SessionModel
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.schemas.agent_run_input import AgentRunInputResponse

client = TestClient(app)


def _create_session() -> SessionModel:
    return SessionRepository().create(
        SessionModel(
            session_id=uuid4(),
            session_workspace_id=uuid4(),
            title="api msg session",
            status="active",
        )
    )


def test_post_session_message_creates_run_and_accepts(monkeypatch) -> None:
    bootstrap_memory_store()
    session = _create_session()

    # 避免打真实 LLM：替换内部 input_service 为接受即返回的桩
    monkeypatch.setattr(
        "agent_service.app.services.session_message_service.SessionMessageService._resolve_input_service",
        lambda self: SimpleNamespace(
            input=lambda run_id, payload: AgentRunInputResponse(run_id=run_id, status="accepted")
        ),
    )

    response = client.post(
        f"/sessions/{session.session_id}/messages",
        json={"content": "hello backend"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    runs = AgentRunRepository().list_by_session_id(session.session_id)
    assert len(runs) == 1


def test_post_session_message_unknown_session_returns_404(monkeypatch) -> None:
    bootstrap_memory_store()
    monkeypatch.setattr(
        "agent_service.app.services.session_message_service.SessionMessageService._resolve_input_service",
        lambda self: SimpleNamespace(
            input=lambda run_id, payload: AgentRunInputResponse(run_id=run_id, status="accepted")
        ),
    )

    response = client.post(
        f"/sessions/{uuid4()}/messages",
        json={"content": "x"},
    )

    assert response.status_code == 404
