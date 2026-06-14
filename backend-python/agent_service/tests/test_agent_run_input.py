from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from uuid import UUID

from fastapi.testclient import TestClient

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.database.memory_store import STORE
from agent_service.app.main import app
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.models.session import SessionModel
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.input_event_repository import InputEventRepository
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.schemas.agent_run_input import AgentRunInputRequest
from agent_service.app.services.agent_run_input_service import AgentRunInputService


client = TestClient(app)


def _create_active_session() -> SessionModel:
    session_workspace = SessionWorkspaceRepository().create(
        SessionWorkspaceModel(
            session_workspace_id=uuid4(),
            source_workspace_id=uuid4(),
            name="branch-a",
            root_path="E:/workspace/branch-a",
            status="ready",
        )
    )
    session = SessionModel(
        session_id=uuid4(),
        session_workspace_id=session_workspace.session_workspace_id,
        title="demo session",
        status="active",
    )
    SessionRepository().create(session)
    return session


def test_orchestrator_input_generates_markdown_plan_file() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.post(
        f"/agent-runs/{run_id}/input",
        json={
            "input_id": str(uuid4()),
            "type": "user_input",
            "payload": {
                "content": (
                    "Create an execution plan for implementing a markdown export feature in a Python "
                    "backend. Use the plan_tool now."
                )
            },
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"run_id": run_id, "status": "accepted"}
    created_run = AgentRunRepository().get_by_id(UUID(run_id))
    assert created_run is not None
    assert created_run.status == "chatting"
    plan = PlanRepository().get_by_run_id(UUID(run_id))
    assert plan is not None
    plan_file = Path(plan.file_path)
    assert plan_file.exists()
    assert plan_file.suffix == ".md"
    assert plan_file.read_text(encoding="utf-8").strip()


def test_worker_callback_input_agent_run() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "worker")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = create_response.json()["run_id"]

    response = client.post(
        f"/agent-runs/{run_id}/input",
        json={
            "input_id": str(uuid4()),
            "type": "worker_callback",
            "payload": {"summary": "done"},
            "idempotency_key": str(uuid4()),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {"run_id": run_id, "status": "accepted"}


def test_agent_run_input_persists_domain_event_for_user_message() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(
        execute=lambda runtime_bundle, request: SimpleNamespace(content="ok", tool_calls=[], raw={})
    )

    response = service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "hello session"},
            idempotency_key=str(uuid4()),
        ),
    )

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None

    events = DomainEventRepository().list_by_session_id(run.session_id)

    assert response.status == "accepted"
    assert any(event.event_type == "session.message.appended" for event in events)


def test_agent_run_input_emits_run_lifecycle_events() -> None:
    bootstrap_memory_store()

    agent_id = next(agent.agent_id for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")
    session = _create_active_session()
    create_response = client.post(
        "/agent-runs",
        json={
            "agent_id": str(agent_id),
            "session_id": str(session.session_id),
            "workspace_id": str(uuid4()),
            "metadata": {},
        },
    )
    run_id = UUID(create_response.json()["run_id"])

    service = AgentRunInputService(
        agent_run_repository=AgentRunRepository(),
        agent_repository=AgentRepository(),
        input_event_repository=InputEventRepository(),
    )
    service.executor_factory = lambda runtime: SimpleNamespace(
        execute=lambda runtime_bundle, request: SimpleNamespace(
            content="agent reply", tool_calls=[], raw={}
        )
    )

    service.input(
        run_id=run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "hello"},
            idempotency_key=str(uuid4()),
        ),
    )

    run = AgentRunRepository().get_by_id(run_id)
    assert run is not None
    events = DomainEventRepository().list_by_session_id(run.session_id)
    event_types = [event.event_type for event in events]

    assert "run.started" in event_types
    assert "run.completed" in event_types
    # agent 回复落事件，且 role 为 assistant
    assert any(
        event.event_type == "session.message.appended"
        and event.payload.get("role") == "assistant"
        and event.payload.get("content") == "agent reply"
        for event in events
    )
    # sequence_no 单调递增
    assert [event.sequence_no for event in events] == sorted(
        event.sequence_no for event in events
    )
