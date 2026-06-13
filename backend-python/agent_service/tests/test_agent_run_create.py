from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from agent_service.app.database.memory_store import STORE
from agent_service.app.main import app
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.models.session import SessionModel
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.schemas.agent_run_create import AgentRunCreateRequest


client = TestClient(app)


def test_create_agent_run() -> None:
    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session_workspace = SessionWorkspaceRepository().create(
        SessionWorkspaceModel(
            session_workspace_id=uuid4(),
            source_workspace_id=uuid4(),
            name="branch-a",
            root_path="E:/workspace/branch-a",
            status="ready",
        )
    )
    session = SessionRepository().create(
        SessionModel(
            session_id=uuid4(),
            session_workspace_id=session_workspace.session_workspace_id,
            title="demo session",
            status="active",
        )
    )
    response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "created"
    assert "run_id" in body
    created_run = AgentRunRepository().get_by_id(UUID(body["run_id"]))
    assert created_run is not None
    assert created_run.runtime_snapshot["role"] == "orchestrator"


def test_create_agent_run_requires_session_id() -> None:
    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")

    response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )

    assert response.status_code == 422


def test_agent_run_repository_round_trips_sqlite_record() -> None:
    repository = AgentRunRepository()
    run = AgentRunModel(
        run_id=uuid4(),
        agent_id=uuid4(),
        role="orchestrator",
        agent_kind="orchestrator",
        workspace_id=uuid4(),
        status="created",
    )

    repository.create(run)
    STORE.agent_runs.clear()
    loaded = repository.get_by_id(run.run_id)

    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.status == "created"


def test_agent_run_model_keeps_session_id() -> None:
    session_id = uuid4()
    run = AgentRunModel(
        run_id=uuid4(),
        session_id=session_id,
        agent_id=uuid4(),
        role="orchestrator",
        agent_kind="orchestrator",
        workspace_id=uuid4(),
        status="created",
    )

    assert run.session_id == session_id


def test_agent_run_create_request_accepts_session_id() -> None:
    payload = AgentRunCreateRequest(
        agent_id=uuid4(),
        session_id=uuid4(),
        workspace_id=uuid4(),
        metadata={},
    )

    assert payload.session_id is not None
