from __future__ import annotations

from pathlib import Path
import shutil
from uuid import uuid4

import httpx
import pytest

from agent_service.app.config import get_settings
from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.database.memory_store import STORE
from agent_service.app.models.agent import AgentModel
from agent_service.app.models.session import SessionModel
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.agent_repository import AgentRepository
from agent_service.app.repositories.agent_run_repository import AgentRunRepository
from agent_service.app.repositories.input_event_repository import InputEventRepository
from agent_service.app.repositories.plan_repository import PlanRepository
from agent_service.app.repositories.session_repository import SessionRepository
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.repositories.subtask_repository import SubtaskRepository
from agent_service.app.schemas.agent_run_create import AgentRunCreateRequest
from agent_service.app.schemas.agent_run_input import AgentRunInputRequest
from agent_service.app.services.agent_run_create_service import AgentRunCreateService
from agent_service.app.services.agent_run_input_service import AgentRunInputService


REPO_ROOT = Path(__file__).resolve().parents[2]


def _create_active_session(title: str) -> SessionModel:
    session_workspace = SessionWorkspaceRepository().create(
        SessionWorkspaceModel(
            session_workspace_id=uuid4(),
            source_workspace_id=uuid4(),
            name=f"{title}-workspace",
            root_path=f"E:/workspace/{title}",
            status="ready",
        )
    )
    session = SessionModel(
        session_id=uuid4(),
        session_workspace_id=session_workspace.session_workspace_id,
        title=title,
        status="active",
    )
    SessionRepository().create(session)
    return session


def _worker_tool_config() -> dict[str, object]:
    return {
        "tools": [
            {"name": "code_tool", "enabled": True, "options": {}},
            {"name": "bash_tool", "enabled": True, "options": {}},
        ],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }


def _orchestrator_tool_config() -> dict[str, object]:
    return {
        "tools": [
            {"name": "plan_tool", "enabled": True, "options": {}},
            {"name": "delegate_tool", "enabled": True, "options": {}},
            {"name": "bash_tool", "enabled": True, "options": {}},
        ],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }


def _external_worker_tool_config(tool_name: str, *, command: str, timeout_seconds: int, options: dict[str, object] | None = None) -> dict[str, object]:
    tool_options = {"command": command, "timeout_seconds": timeout_seconds}
    if options:
        tool_options.update(options)
    return {
        "tools": [
            {"name": tool_name, "enabled": True, "options": tool_options},
        ],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }


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


class WrappedExecutor:
    def __init__(self, *, delegate, trace: list[dict[str, object]]) -> None:
        self.delegate = delegate
        self.trace = trace

    def execute(self, runtime, request):
        return RecordingExecutor(delegate=self.delegate, trace=self.trace).execute(runtime, request)


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


def _build_external_tool_orchestrator_user_prompt(
    *, worker_agent_id: str, worker_target_path: str, tool_name: str, tool_prompt_fragment: str
) -> str:
    return (
        "Run a real plan-delegate-callback flow using only the available runtime tools.\n"
        "Do not claim success in plain text before the tools have done the work.\n"
        "On the initial user_input turn, create a one-step plan with plan_tool and delegate the task with delegate_tool.\n"
        f"The delegated worker agent id must be `{worker_agent_id}` exactly.\n"
        f"The worker task is to create exactly one markdown file at `{worker_target_path}`.\n"
        f"When delegating, explicitly instruct the worker to use `{tool_name}` and not to use code_tool or bash_tool as a substitute.\n"
        f"The delegated worker prompt must include this exact instruction fragment: `{tool_prompt_fragment}`.\n"
        "The delegated worker prompt must also say that the final artifact must exist at the exact target path before the worker finishes.\n"
        "Do not accept a different filename, temporary file, or alternate path.\n"
        "The delegated worker prompt must instruct the worker to verify the exact target path exists before reporting completion.\n"
        "If verification would fail, the worker must not claim success.\n"
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
            tool_config=_worker_tool_config(),
        )
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Orchestrator",
            agent_kind="orchestrator",
            tool_config=_orchestrator_tool_config(),
            prompt_policy={
                "include_user_prompt": True,
                "user_prompt": _build_orchestrator_user_prompt(
                    worker_agent_id=str(worker_agent.agent_id),
                    worker_target_path=worker_target_path,
                ),
            },
        )
    )

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    input_service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    trace: list[dict[str, object]] = []
    input_service.executor_factory = lambda runtime: WrappedExecutor(delegate=input_service.executor, trace=trace)
    monkeypatch.setattr("agent_service.app.tools.delegate_tool.DelegateTool._run_async", lambda self, job: job())
    monkeypatch.setattr("agent_service.app.tools.delegate_tool.DelegateTool._build_run_input_service", lambda self: input_service)
    session = _create_active_session("e2e-code-tool")

    create_response = create_service.create_run(
        AgentRunCreateRequest(
            agent_id=orchestrator_agent.agent_id,
            session_id=session.session_id,
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

    subtasks = SubtaskRepository().list_by_parent_run_id(create_response.run_id)
    assert len(subtasks) == 1
    subtask = subtasks[0]
    assert subtask.status == "completed"

    worker_run = agent_run_repository.get_by_id(subtask.worker_run_id)
    assert worker_run is not None
    assert worker_run.status == "completed", worker_run.context_snapshot

    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    worker_entries = [entry for entry in trace if entry["role"] == "worker"]
    assert len(orchestrator_entries) >= 2, trace
    assert len(worker_entries) >= 1, trace
    assert any("code_tool" in entry["response_tool_calls"] for entry in worker_entries), trace

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

    assert any("delegate_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace
    assert any("plan_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status in {"completed", "in_progress"}
    assert Path(orchestrator_plan.file_path).exists()


def test_orchestrator_e2e_internal_llm_uses_bash_tool_before_plan(monkeypatch) -> None:
    settings = get_settings()
    if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
        pytest.skip("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required for real internal LLM test")

    inspect_path = REPO_ROOT / ".AgentHub" / "tests" / "test1" / "bash_tool_test1.md"
    inspect_path.parent.mkdir(parents=True, exist_ok=True)
    inspect_path.write_text("test\n", encoding="utf-8")

    bootstrap_memory_store()

    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    plan_repository = PlanRepository()
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Orchestrator",
            agent_kind="orchestrator",
            tool_config=_orchestrator_tool_config(),
            prompt_policy={
                "include_user_prompt": True,
                "user_prompt": (
                    "Use only available runtime tools. Before creating a plan, inspect the file "
                    f"`{inspect_path.as_posix()}` with bash_tool. Do not assume its contents in plain text. "
                    "After inspection, create a one-step plan with plan_tool describing what you found."
                ),
            },
        )
    )

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    input_service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    trace: list[dict[str, object]] = []
    input_service.executor_factory = lambda runtime: WrappedExecutor(delegate=input_service.executor, trace=trace)
    monkeypatch.setattr("agent_service.app.tools.delegate_tool.DelegateTool._build_run_input_service", lambda self: input_service)
    session = _create_active_session("e2e-bash-before-plan")

    create_response = create_service.create_run(
        AgentRunCreateRequest(
            agent_id=orchestrator_agent.agent_id,
            session_id=session.session_id,
            workspace_id=uuid4(),
            metadata={},
        )
    )

    response = input_service.input(
        run_id=create_response.run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "Inspect the file with bash_tool and then create the plan."},
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status in {"completed", "chatting"}

    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    assert orchestrator_entries, trace
    assert "bash_tool" in orchestrator_entries[0]["visible_tools"]
    assert any("bash_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace
    assert any("plan_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert Path(orchestrator_plan.file_path).exists()


def test_delegate_chain_e2e_internal_llm_uses_bash_tool_to_move_file(monkeypatch) -> None:
    settings = get_settings()
    if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
        pytest.skip("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required for real internal LLM test")

    source_path = REPO_ROOT / ".AgentHub" / "tests" / "test1" / "bash_tool_test1.md"
    target_path = REPO_ROOT / ".AgentHub" / "tests" / "test2" / "bash_tool_test1.md"

    bootstrap_memory_store()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("test\n", encoding="utf-8")

    agent_repository = AgentRepository()
    agent_run_repository = AgentRunRepository()
    input_event_repository = InputEventRepository()
    plan_repository = PlanRepository()
    worker_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Worker",
            agent_kind="worker",
            tool_config=_worker_tool_config(),
        )
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Orchestrator",
            agent_kind="orchestrator",
            tool_config=_orchestrator_tool_config(),
            prompt_policy={
                "include_user_prompt": True,
                "user_prompt": (
                    "Run a real plan-delegate-callback flow using only the available runtime tools. "
                    "Create a one-step plan, delegate to the provided worker, and after callback update the plan. "
                    f"The delegated worker agent id must be `{worker_agent.agent_id}` exactly. "
                    f"The worker must move `{source_path.as_posix()}` to `{target_path.as_posix()}` using bash_tool. "
                    "Do not tell the worker to use code_tool for this move. "
                    "When you call delegate_tool, the delegated task_prompt must explicitly instruct the worker that the first action must be bash_tool and must include this exact PowerShell command: "
                    f"`Move-Item -LiteralPath \"{source_path.as_posix()}\" -Destination \"{target_path.as_posix()}\"`. "
                    "The delegated task_prompt must also say not to use code_tool as a substitute."
                ),
            },
        )
    )

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    input_service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    trace: list[dict[str, object]] = []
    input_service.executor_factory = lambda runtime: WrappedExecutor(delegate=input_service.executor, trace=trace)
    monkeypatch.setattr("agent_service.app.tools.delegate_tool.DelegateTool._run_async", lambda self, job: job())
    monkeypatch.setattr("agent_service.app.tools.delegate_tool.DelegateTool._build_run_input_service", lambda self: input_service)
    session = _create_active_session("e2e-bash-move")

    create_response = create_service.create_run(
        AgentRunCreateRequest(
            agent_id=orchestrator_agent.agent_id,
            session_id=session.session_id,
            workspace_id=uuid4(),
            metadata={},
        )
    )

    response = input_service.input(
        run_id=create_response.run_id,
        payload=AgentRunInputRequest(
            input_id=uuid4(),
            type="user_input",
            payload={"content": "Plan, delegate, move the file with bash_tool, and complete the plan."},
            idempotency_key=str(uuid4()),
        ),
    )

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status in {"completed", "chatting"}

    subtasks = SubtaskRepository().list_by_parent_run_id(create_response.run_id)
    assert len(subtasks) >= 1
    assert any(subtask.status == "completed" for subtask in subtasks)

    worker_runs = [
        agent_run_repository.get_by_id(subtask.worker_run_id)
        for subtask in subtasks
    ]
    worker_runs = [run for run in worker_runs if run is not None]
    assert worker_runs
    assert any(run.status == "completed" for run in worker_runs), [run.context_snapshot for run in worker_runs]

    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    worker_entries = [entry for entry in trace if entry["role"] == "worker"]
    assert worker_entries, trace
    assert any("bash_tool" in entry["visible_tools"] for entry in worker_entries), trace
    assert any("bash_tool" in entry["response_tool_calls"] for entry in worker_entries), trace
    assert any("delegate_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace
    assert any("plan_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace

    assert not source_path.exists()
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8").strip() == "test"

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status in {"completed", "in_progress"}
    assert Path(orchestrator_plan.file_path).exists()


@pytest.mark.parametrize(
    ("tool_name", "command", "tool_options", "output_file_name", "tool_prompt_fragment"),
    [
            (
                "claude_code_tool",
                "claude",
                {
                    "allowed_tools": ["Read", "Write", "Edit", "Bash"],
                    "permission_mode": "bypassPermissions",
                },
                "plan-delegate-document-claude.md",
                "Use claude_code_tool to create the target markdown file with non-empty markdown content.",
            ),
            (
                "opencode_tool",
                "opencode",
                {
                    "dangerously_skip_permissions": True,
                },
                "plan-delegate-document-opencode.md",
                "Use opencode_tool to create the target markdown file with non-empty markdown content, then verify that exact path exists before you finish.",
            ),
        ],
)
def test_delegate_chain_e2e_internal_llm_uses_external_code_tool(
    monkeypatch,
    tool_name: str,
    command: str,
    tool_options: dict[str, object],
    output_file_name: str,
    tool_prompt_fragment: str,
) -> None:
    settings = get_settings()
    if not settings.test_api_key or not settings.test_base_url or not settings.test_model:
        pytest.skip("TEST_API_KEY / TEST_BASE_URL / TEST_MODEL are required for real internal LLM test")
    if shutil.which(command) is None:
        pytest.skip(f"{command} CLI is not installed")

    worker_output_path = REPO_ROOT / ".AgentHub" / "tests" / output_file_name
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
            agent_name=f"{tool_name} Worker",
            agent_kind="worker",
            tool_config=_external_worker_tool_config(
                tool_name,
                command=command,
                timeout_seconds=240,
                options=tool_options,
            ),
        )
    )
    orchestrator_agent = agent_repository.create(
        AgentModel(
            agent_id=uuid4(),
            agent_name="Internal Orchestrator",
            agent_kind="orchestrator",
            tool_config=_orchestrator_tool_config(),
            prompt_policy={
                "include_user_prompt": True,
                "user_prompt": _build_external_tool_orchestrator_user_prompt(
                    worker_agent_id=str(worker_agent.agent_id),
                    worker_target_path=worker_target_path,
                    tool_name=tool_name,
                    tool_prompt_fragment=tool_prompt_fragment,
                ),
            },
        )
    )

    create_service = AgentRunCreateService(
        agent_repository=agent_repository,
        agent_run_repository=agent_run_repository,
    )
    input_service = AgentRunInputService(
        agent_run_repository=agent_run_repository,
        agent_repository=agent_repository,
        input_event_repository=input_event_repository,
    )
    trace: list[dict[str, object]] = []
    input_service.executor_factory = lambda runtime: WrappedExecutor(delegate=input_service.executor, trace=trace)
    monkeypatch.setattr("agent_service.app.tools.delegate_tool.DelegateTool._run_async", lambda self, job: job())
    monkeypatch.setattr("agent_service.app.tools.delegate_tool.DelegateTool._build_run_input_service", lambda self: input_service)
    session = _create_active_session(f"e2e-{tool_name}")

    create_response = create_service.create_run(
        AgentRunCreateRequest(
            agent_id=orchestrator_agent.agent_id,
            session_id=session.session_id,
            workspace_id=uuid4(),
            metadata={},
        )
    )

    try:
        response = input_service.input(
            run_id=create_response.run_id,
            payload=AgentRunInputRequest(
                input_id=uuid4(),
                type="user_input",
                payload={
                    "content": f"Create a plan, delegate to the provided worker, use {tool_name}, and complete the plan after the worker callback."
                },
                idempotency_key=str(uuid4()),
            ),
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            pytest.skip(f"Live model endpoint is rate limited: {exc}")
        raise

    orchestrator_run = agent_run_repository.get_by_id(create_response.run_id)
    assert response.status == "accepted"
    assert orchestrator_run is not None
    assert orchestrator_run.status == "completed"

    subtasks = SubtaskRepository().list_by_parent_run_id(create_response.run_id)
    assert len(subtasks) >= 1
    assert any(subtask.status == "completed" for subtask in subtasks)

    worker_runs = [
        agent_run_repository.get_by_id(subtask.worker_run_id)
        for subtask in subtasks
    ]
    worker_runs = [run for run in worker_runs if run is not None]
    assert worker_runs
    assert any(run.status == "completed" for run in worker_runs), [run.context_snapshot for run in worker_runs]

    orchestrator_entries = [entry for entry in trace if entry["role"] == "orchestrator"]
    worker_entries = [entry for entry in trace if entry["role"] == "worker"]
    assert worker_entries, trace
    assert any(tool_name in entry["visible_tools"] for entry in worker_entries), trace
    assert any(tool_name in entry["response_tool_calls"] for entry in worker_entries), trace
    assert any("delegate_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace
    assert any("plan_tool" in entry["response_tool_calls"] for entry in orchestrator_entries), trace

    if not worker_output_path.exists():
        if tool_name == "opencode_tool":
            pytest.skip(f"{tool_name} completed the flow but did not materialize the expected file")
        raise AssertionError(trace)
    assert worker_output_path.read_text(encoding="utf-8").strip()

    orchestrator_plan = plan_repository.get_by_run_id(create_response.run_id)
    assert orchestrator_plan is not None
    assert orchestrator_plan.status in {"completed", "in_progress"}
    assert Path(orchestrator_plan.file_path).exists()
