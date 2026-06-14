from uuid import uuid4

from fastapi.testclient import TestClient

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.main import app
from agent_service.app.models.domain_event import DomainEventModel
from agent_service.app.models.session import SessionModel
from agent_service.app.models.subtask import SubtaskModel
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.repositories.subtask_repository import SubtaskRepository

client = TestClient(app)


def _create_session() -> SessionModel:
    session = SessionModel(
        session_id=uuid4(),
        session_workspace_id=uuid4(),
        title="read api session",
        status="active",
    )
    return SessionRepository().create(session)


def test_list_sessions_includes_created() -> None:
    bootstrap_memory_store()
    session = _create_session()

    response = client.get("/sessions")

    assert response.status_code == 200
    ids = {item["session_id"] for item in response.json()}
    assert str(session.session_id) in ids


def test_get_session_returns_detail_and_404() -> None:
    bootstrap_memory_store()
    session = _create_session()

    ok = client.get(f"/sessions/{session.session_id}")
    assert ok.status_code == 200
    assert ok.json()["session_id"] == str(session.session_id)

    missing = client.get(f"/sessions/{uuid4()}")
    assert missing.status_code == 404


def test_get_session_events_since_filters() -> None:
    bootstrap_memory_store()
    session = _create_session()
    repo = DomainEventRepository()
    for seq in (1, 2, 3):
        repo.create(
            DomainEventModel(
                event_id=uuid4(),
                session_id=session.session_id,
                session_workspace_id=session.session_workspace_id,
                event_type="run.started",
                event_scope="main_timeline",
                sequence_no=seq,
                payload={"n": seq},
            )
        )

    response = client.get(f"/sessions/{session.session_id}/events", params={"since": 1})

    assert response.status_code == 200
    seqs = [item["sequence_no"] for item in response.json()]
    assert seqs == [2, 3]


def test_get_session_subtasks() -> None:
    bootstrap_memory_store()
    session = _create_session()
    SubtaskRepository().create(
        SubtaskModel(
            subtask_id=uuid4(),
            session_id=session.session_id,
            root_run_id=uuid4(),
            parent_run_id=uuid4(),
            task_prompt="t",
        )
    )

    response = client.get(f"/sessions/{session.session_id}/subtasks")

    assert response.status_code == 200
    assert len(response.json()) >= 1
