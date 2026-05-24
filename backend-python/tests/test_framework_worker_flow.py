from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.input_event_repository import InputEventRepository
from app.schemas.agent_run_input import AgentRunInputRequest
from app.services.agent_run_input_service import AgentRunInputService


def _build_framework_service() -> tuple[AgentRunInputService, AgentRepository, AgentRunRepository]:
    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    return service, agent_repository, agent_run_repository


def test_framework_worker_input_completes_and_persists_result(monkeypatch) -> None:
    service, agent_repository, agent_run_repository = _build_framework_service()
    agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Claude Worker",
            agent_kind="worker",
            executor_policy={"kind": "framework_cli", "framework": "claude"},
        )
    )
    run = agent_run_repository.create(
        AgentRunModel(
            run_id=uuid4(),
            agent_id=agent.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
            runtime_snapshot={
                "role": "worker",
                "executor_policy": {"kind": "framework_cli", "framework": "claude"},
            },
        )
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout='{"content":"done by claude"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    response = service.input(
        run.run_id,
        AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "implement feature"},
            idempotency_key=str(uuid4()),
        ),
    )

    updated_run = agent_run_repository.get_by_id(run.run_id)

    assert response.status == "accepted"
    assert updated_run is not None
    assert updated_run.status == "completed"
    assert updated_run.context_snapshot["framework_execution"]["content"] == "done by claude"
    assert updated_run.context_snapshot["framework_execution"]["framework"] == "claude"


def test_framework_worker_input_marks_run_failed_on_executor_error(monkeypatch) -> None:
    service, agent_repository, agent_run_repository = _build_framework_service()
    agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Claude Worker",
            agent_kind="worker",
            executor_policy={"kind": "framework_cli", "framework": "claude"},
        )
    )
    run = agent_run_repository.create(
        AgentRunModel(
            run_id=uuid4(),
            agent_id=agent.agent_id,
            agent_kind=agent.agent_kind,
            workspace_id=uuid4(),
            root_run_id=uuid4(),
            runtime_snapshot={
                "role": "worker",
                "executor_policy": {"kind": "framework_cli", "framework": "claude"},
            },
        )
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="", stderr="boom", returncode=1)

    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="framework executor failed"):
        service.input(
            run.run_id,
            AgentRunInputRequest(
                input_id=uuid4(),
                type="user_input",
                payload={"content": "implement feature"},
                idempotency_key=str(uuid4()),
            ),
        )

    updated_run = agent_run_repository.get_by_id(run.run_id)

    assert updated_run is not None
    assert updated_run.status == "failed"
    assert "framework executor failed" in updated_run.context_snapshot["framework_execution"]["error"]
