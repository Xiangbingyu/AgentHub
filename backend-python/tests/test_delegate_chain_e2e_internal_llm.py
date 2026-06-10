from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.config import get_settings
from app.database.bootstrap import bootstrap_memory_store
from app.database.memory_store import STORE
from app.llm.llm_executor import AgentExecutorFactory
from app.models.agent import AgentModel
from app.repositories.agent_repository import AgentRepository
from app.repositories.agent_run_repository import AgentRunRepository
from app.repositories.input_event_repository import InputEventRepository
from app.repositories.plan_repository import PlanRepository
from app.schemas.agent_run_create import AgentRunCreateRequest
from app.schemas.agent_run_input import AgentRunInputRequest
from app.services.agent_run_create_service import AgentRunCreateService
from app.services.agent_run_input_service import AgentRunInputService


REPO_ROOT = Path(__file__).resolve().parents[1]


class RecordingExecutor:
    def __init__(self, *, delegate, trace: list[dict[str, object]]) -> None:
        self.delegate = delegate
        self.trace = trace

    def execute(self, runtime, request):
        entry = {
            "role": runtime.role,
            "run_id": str(runtime.agent_run.run_id),
            "visible_tools": [tool["function"]["name"] for tool in request.tools],
            "message_content": request.messages[0].content if request.messages else "",
        }
        response = self.delegate.execute(runtime, request)
        entry["response_content"] = response.content
        entry["response_tool_calls"] = [
            tool_call.get("function", {}).get("name")
            for tool_call in response.tool_calls
            if tool_call.get("function", {}).get("name")
        ]
        entry["response_raw"] = response.raw
        self.trace.append(entry)
        return response


def _build_orchestrator_user_prompt(*, worker_agent_id: str, worker_target_path: str) -> str:
    return (
        "Run a real plan-delegate-callback flow using only the available runtime tools.\n"
        "Do not claim success in plain text before the tools have done the work.\n"
        "On the initial user_input turn, create a one-step plan with plan_tool and delegate the task with delegate_tool.\n"
        f"The delegated worker agent id must be `{worker_agent_id}` exactly.\n"
        f"The worker task is to create the Python file `{worker_target_path}` with non-empty example code.\n"
        "When delegating, explicitly instruct the worker to use code_tool for the file write and not to only describe the intended action.\n"
        "After the worker_callback arrives, inspect the callback result and update the plan with plan_tool.\n"
        "If the worker succeeded, mark the single step as completed and summarize the result.\n"
        "Do not delegate again after the callback.\n"
        "Do not invent completion without a worker callback."
    )


def test_delegate_chain_e2e_internal_llm_uses_code_tool(monkeypatch) -> None:
    settings = get_settings()
    if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
        pytest.skip("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required for real internal LLM test")

    worker_output_path = REPO_ROOT / ".AgentHub" / "tests" / "internal-llm-code-tool-example.py"
    worker_target_path = worker_output_path.as_posix()

    bootstrap_memory_store()
    worker_output_path.parent.mkdir(parents=True, exist_ok=True)
    if worker_output_path.exists():
        worker_output_path.unlink()

    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    plan_repository = PlanRepository()
    worker_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Worker",
            agent_kind="worker",
        )
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Orchestrator",
            agent_kind="orchestrator",
            prompt_policy={
                "include_user_prompt": True,
                "user_prompt": _build_orchestrator_user_prompt(
                    worker_agent_id=str(worker_agent.agent_id),
                    worker_target_path=worker_target_path,
                ),
            },
        )
    )

    trace: list[dict[str, object]] = []
    original_resolve = AgentExecutorFactory.resolve

    def recording_resolve(self, runtime):
        return RecordingExecutor(delegate=original_resolve(self, runtime), trace=trace)

    monkeypatch.setattr(AgentExecutorFactory, "resolve", recording_resolve)
    monkeypatch.setattr("app.tools.delegate_tool.DelegateTool._run_async", lambda self, job: job())

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    input_service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )

    create_response = create_service.create_run(
        AgentRunCreateRequest(
            agent_id=orchestrator_agent.agent_id,
            workspace_id=uuid4(),
            metadata={},
        )
    )

    response = input_service.input(
        run_id=create_response.run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={
                "content": "Create a plan, delegate to the provided internal worker, and complete the plan after the worker callback."
            },
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status == "completed"

    subtasks = list(STORE.subtasks.values())
    assert len(subtasks) == 1
    subtask = subtasks[0]
    assert subtask.status == "completed"

    worker_run = agent_run_repository.get_by_id(subtask.worker_run_id)
    assert worker_run is not None
    assert worker_run.status == "completed", worker_run.context_snapshot

    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    worker_entries = [entry for entry in trace if entry["role"] == "worker"]
    assert len(orchestrator_entries) == 2, trace
    assert len(worker_entries) == 1, trace
    assert worker_entries[0]["response_tool_calls"] == ["code_tool"], worker_entries[0]["response_raw"]

    assert worker_output_path.exists(), {
        "trace": trace,
        "worker_context": worker_run.context_snapshot,
        "orchestrator_context": orchestrator_run.context_snapshot,
        "plans": {
            str(run_id): {
                "status": plan.status,
                "file_path": plan.file_path,
                "title": plan.title,
                "summary": plan.summary,
            }
            for run_id, plan in STORE.plans.items()
        },
    }
    assert worker_output_path.read_text(encoding="utf-8").strip()

    assert orchestrator_entries[0]["response_tool_calls"] == ["plan_tool", "delegate_tool"], trace
    assert orchestrator_entries[1]["response_tool_calls"] == ["plan_tool"], trace

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status == "completed"
    assert Path(orchestrator_plan.file_path).exists()
