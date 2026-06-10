from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.llm.llm_executor import AgentExecutorFactory
from app.llm.llm_types import LlmResponse
from app.models.agent import AgentModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.input_event_repository import InputEventRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.agent_run_create import AgentRunCreateRequest
from app.schemas.agent_run_input import AgentRunInputRequest
from app.services.agent_run_create_service import AgentRunCreateService
from app.services.agent_run_input_service import AgentRunInputService


class SequencedExecutor:
    def __init__(self, responses: list[LlmResponse]) -> None:
        self.responses = responses
        self.calls = []

    def execute(self, runtime, request):
        self.calls.append(
            {
                "role": runtime.role,
                "run_id": runtime.agent_run.run_id,
                "tools": [tool["function"]["name"] for tool in request.tools],
                "content": request.messages[0].content if request.messages else "",
            }
        )
        if not self.responses:
            raise AssertionError("no response prepared for executor")
        return self.responses.pop(0)


def test_delegate_chain_internal_worker_uses_bash_tool_to_move_workspace_file(monkeypatch) -> None:
    bootstrap_memory_store()

    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    plan_repository = PlanRepository()

    worker_agent = agent_repository.create(
        AgentModel(agent_id=uuid4(), agent_name="Internal Worker", agent_kind="worker")
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(agent_id=uuid4(), agent_name="Internal Orchestrator", agent_kind="orchestrator")
    )

    repo_root = Path(__file__).resolve().parents[1]
    source_path = repo_root / ".AgentHub" / "tests" / "test1" / "bash_tool_test1.md"
    target_path = repo_root / ".AgentHub" / "tests" / "test2" / "bash_tool_test1.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("test\n", encoding="utf-8")
    if target_path.exists():
        target_path.unlink()

    executor = SequencedExecutor(
        responses=[
            LlmResponse(
                content="planned and delegated",
                tool_calls=[
                    {
                        "id": "tool_1",
                        "type": "function",
                        "function": {
                            "name": "plan_tool",
                            "arguments": (
                                '{"plan":{"title":"Move file","goal":"Move delegated test file",'
                                '"summary":"Delegate file move to worker","steps":[{"step_id":"1",'
                                '"content":"Move delegated test file","status":"pending","priority":"high"}]}}'
                            ),
                        },
                    },
                    {
                        "id": "tool_2",
                        "type": "function",
                        "function": {
                            "name": "delegate_tool",
                            "arguments": (
                                '{"worker_agent_id":"%s","task_prompt":"Use bash_tool to move the file %s to %s '
                                'and do not use code_tool for this move.","summary":"delegated file move"}'
                            )
                            % (worker_agent.agent_id, source_path.as_posix(), target_path.as_posix()),
                        },
                    },
                ],
                raw={"provider": "test"},
            ),
            LlmResponse(
                content="worker moved file",
                tool_calls=[
                    {
                        "id": "tool_3",
                        "type": "function",
                        "function": {
                            "name": "bash_tool",
                            "arguments": json.dumps(
                                {
                                    "command": (
                                        f'Move-Item -LiteralPath "{source_path}" -Destination "{target_path}"'
                                    ),
                                    "description": "Moves delegated test file",
                                }
                            ),
                        },
                    }
                ],
                raw={"provider": "test"},
            ),
            LlmResponse(
                content="plan completed",
                tool_calls=[
                    {
                        "id": "tool_4",
                        "type": "function",
                        "function": {
                            "name": "plan_tool",
                            "arguments": (
                                '{"plan":{"title":"Move file","goal":"Move delegated test file",'
                                '"summary":"Delegated file moved","steps":[{"step_id":"1",'
                                '"content":"Move delegated test file","status":"completed","priority":"high"}]}}'
                            ),
                        },
                    }
                ],
                raw={"provider": "test"},
            ),
        ]
    )

    service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    monkeypatch.setattr(AgentExecutorFactory, "resolve", lambda self, runtime: executor)
    monkeypatch.setattr("app.tools.delegate_tool.DelegateTool._run_async", lambda self, job: job())

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    create_response = create_service.create_run(
        AgentRunCreateRequest(agent_id=orchestrator_agent.agent_id, workspace_id=uuid4(), metadata={})
    )

    response = service.input(
        create_response.run_id,
        AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "plan, delegate, and move the test file with bash_tool"},
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    subtasks = list(STORE.subtasks.values())
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status == "completed"
    assert len(subtasks) == 1

    worker_run = agent_run_repository.get_by_id(subtasks[0].worker_run_id)
    assert worker_run is not None
    assert worker_run.status == "completed"
    assert not source_path.exists()
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8").strip() == "test"

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status == "completed"

    assert [call["role"] for call in executor.calls] == ["orchestrator", "worker", "orchestrator"]
    assert executor.calls[0]["tools"] == ["plan_tool", "delegate_tool", "bash_tool"]
    assert executor.calls[1]["tools"] == ["code_tool", "bash_tool"]
