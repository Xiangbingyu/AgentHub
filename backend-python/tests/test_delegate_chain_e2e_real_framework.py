from __future__ import annotations
import shutil
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
            "status_before": runtime.agent_run.status,
            "executor_kind": runtime.executor_policy.get("kind"),
            "executor_provider": runtime.executor_policy.get("provider") or runtime.executor_policy.get("framework"),
            "message_content": request.messages[0].content if request.messages else "",
            "visible_tools": [tool["function"]["name"] for tool in request.tools],
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


def _write_trace_file(
    trace: list[dict[str, object]],
    *,
    orchestrator_run_id: str,
    worker_run_id: str,
    worker_output_path: Path,
    trace_output_path: Path,
) -> None:
    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    worker_entries = [entry for entry in trace if entry["role"] == "worker"]
    worker_file_exists = worker_output_path.exists()
    worker_file_content = worker_output_path.read_text(encoding="utf-8") if worker_file_exists else ""

    orchestrator_plan = STORE.plans[next(run_id for run_id in STORE.plans if str(run_id) == orchestrator_run_id)]
    worker_plan = next((plan for run_id, plan in STORE.plans.items() if str(run_id) == worker_run_id), None)
    orchestrator_run = STORE.agent_runs[next(run_id for run_id in STORE.agent_runs if str(run_id) == orchestrator_run_id)]
    worker_run = STORE.agent_runs[next(run_id for run_id in STORE.agent_runs if str(run_id) == worker_run_id)]

    lines = [
        "# Delegate Chain E2E Trace",
        "",
        "## Artifacts",
        f"- Worker markdown file: `{worker_output_path}`",
        f"- Worker markdown exists: `{worker_file_exists}`",
        f"- Orchestrator plan file: `{orchestrator_plan.file_path}`",
        f"- Orchestrator plan exists: `{Path(orchestrator_plan.file_path).exists()}`",
        f"- Worker plan file: `{worker_plan.file_path if worker_plan is not None else ''}`",
        f"- Worker plan exists: `{Path(worker_plan.file_path).exists() if worker_plan is not None else False}`",
        "",
        "## Run Status",
        f"- Orchestrator final status: `{orchestrator_run.status}`",
        f"- Worker final status: `{worker_run.status}`",
        "",
        "## Orchestrator Executions",
    ]

    for index, entry in enumerate(orchestrator_entries, start=1):
        lines.extend(
            [
                f"### Orchestrator #{index}",
                f"- Status before: `{entry['status_before']}`",
                f"- Visible tools: `{', '.join(entry['visible_tools'])}`",
                "",
                "```text",
                str(entry["message_content"]).strip(),
                "```",
                "",
                f"- Response: `{entry['response_content']}`",
                f"- Tool calls: `{', '.join(entry['response_tool_calls'])}`",
                "",
            ]
        )

    lines.extend(["## Worker Execution"])
    for index, entry in enumerate(worker_entries, start=1):
        lines.extend(
            [
                f"### Worker #{index}",
                f"- Status before: `{entry['status_before']}`",
                "",
                "```text",
                str(entry["message_content"]).strip(),
                "```",
                "",
                "```text",
                str(entry["response_content"]).strip(),
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## Plan Documents",
            "### Orchestrator Plan",
            "```md",
            orchestrator_plan.raw_document.strip(),
            "```",
            "",
            "## Worker File",
            "```md",
            worker_file_content.strip(),
            "```",
            "",
        ]
    )
    if worker_plan is not None:
        lines.extend(
            [
                "### Worker Plan",
                "```md",
                worker_plan.raw_document.strip(),
                "```",
                "",
            ]
        )
    trace_output_path.parent.mkdir(parents=True, exist_ok=True)
    trace_output_path.write_text("\n".join(lines), encoding="utf-8")


def _build_worker_output_path(framework: str) -> Path:
    return REPO_ROOT / ".AgentHub" / "tests" / f"plan-delegate-document-{framework}.md"


def _build_orchestrator_user_prompt(*, worker_agent_id: str, worker_target_path: str) -> str:
    return (
        "Run a real plan-delegate-callback flow.\n"
        "Use runtime tools instead of claiming success in plain text.\n"
        "On the initial user_input turn, call plan_tool and delegate_tool in the same response.\n"
        "The plan must contain exactly one step that tracks creation of the markdown file "
        f"`{worker_target_path}`.\n"
        f"When calling delegate_tool, you must use worker_agent_id `{worker_agent_id}` exactly.\n"
        "The delegated task must instruct the worker to create that markdown file with non-empty markdown content and to avoid changing any other file.\n"
        "After a worker_callback arrives, inspect the callback payload and call plan_tool again.\n"
        "If the worker succeeded, mark the single step as completed and summarize the completed result.\n"
        "Do not delegate again after the callback.\n"
        "Do not invent completion without a worker callback."
    )


def _build_worker_executor_policy(framework: str) -> dict[str, object]:
    if framework == "claude":
        return {
            "kind": "framework_cli",
            "framework": "claude",
            "command": "claude",
            "timeout_seconds": 240,
            "permission_mode": "bypassPermissions",
            "framework_allowed_tools": ["Read", "Write", "Edit", "Bash"],
        }
    return {
        "kind": "framework_cli",
        "framework": "opencode",
        "command": "opencode",
        "timeout_seconds": 240,
        "framework_options": {"dangerously_skip_permissions": True},
    }


@pytest.mark.parametrize("framework", ["claude", "opencode"])
def test_delegate_chain_e2e_real_framework(monkeypatch, tmp_path: Path, framework: str) -> None:
    settings = get_settings()
    if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
        pytest.skip("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required for a fully real orchestrator test")
    if shutil.which(framework) is None:
        pytest.skip(f"{framework} CLI is not installed")

    worker_output_path = _build_worker_output_path(framework)
    worker_target_path = worker_output_path.as_posix()
    trace_output_path = tmp_path / f"delegate-chain-e2e-trace-{framework}.md"

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
            agent_name=f"{framework.title()} Worker",
            agent_kind="worker",
            executor_policy=_build_worker_executor_policy(framework),
        )
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Trace Orchestrator",
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
    orchestrator_run_id = create_response.run_id

    response = input_service.input(
        run_id=orchestrator_run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={
                "content": (
                    "Create a one-step plan, delegate the document creation task to the provided worker, "
                    "then complete the plan after the worker callback."
                )
            },
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(orchestrator_run_id)
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status == "completed"

    subtasks = list(STORE.subtasks.values())
    assert len(subtasks) == 1
    subtask = subtasks[0]
    assert subtask.status == "completed"

    worker_run = agent_run_repository.get_by_id(subtask.worker_run_id)
    assert worker_run is not None
    assert worker_run.status == "completed"

    assert worker_output_path.exists()
    assert worker_output_path.read_text(encoding="utf-8").strip()

    orchestrator_events = input_event_repository.list_by_run_id(orchestrator_run_id)
    worker_events = input_event_repository.list_by_run_id(worker_run.run_id)
    assert [event.type.value for event in orchestrator_events] == ["user_input", "worker_callback"]
    assert [event.type.value for event in worker_events] == ["user_input"]

    assert len([entry for entry in trace if entry["role"] == "orchestrator"]) == 2
    assert len([entry for entry in trace if entry["role"] == "worker"]) == 1
    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    assert orchestrator_entries[0]["response_tool_calls"] == ["plan_tool", "delegate_tool"]
    assert orchestrator_entries[1]["response_tool_calls"] == ["plan_tool"]

    worker_execution = worker_run.context_snapshot["framework_execution"]
    assert worker_execution["status"] == "completed"
    assert worker_execution["content"].strip()

    orchestrator_plan = plan_repository.get_by_run_id(orchestrator_run_id)
    worker_plan = plan_repository.get_by_run_id(worker_run.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status == "completed"
    assert orchestrator_plan.title.strip()
    assert orchestrator_plan.goal.strip()
    assert len(orchestrator_plan.steps) == 1
    assert orchestrator_plan.steps[0]["status"] == "completed"
    assert worker_target_path in orchestrator_plan.raw_document
    assert "- [x]" in orchestrator_plan.raw_document
    assert Path(orchestrator_plan.file_path).exists()
    assert Path(orchestrator_plan.file_path).parent == REPO_ROOT / ".AgentHub" / "plans"
    assert worker_plan is None

    _write_trace_file(
        trace,
        orchestrator_run_id=str(orchestrator_run_id),
        worker_run_id=str(worker_run.run_id),
        worker_output_path=worker_output_path,
        trace_output_path=trace_output_path,
    )
    assert trace_output_path.exists()
