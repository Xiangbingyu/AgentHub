from types import SimpleNamespace
from uuid import uuid4

from app.config import get_settings
from app.llm.framework_adapters.claude_code_adapter import ClaudeCodeAdapter
from app.llm.framework_adapters.codex_cli_adapter import CodexCliAdapter
from app.llm.framework_adapters.opencode_adapter import OpenCodeAdapter
from app.llm.llm_executor import (
    AgentExecutorFactory,
    FrameworkCliExecutor,
    InternalLlmExecutor,
    LlmExecutor,
    resolve_framework_adapter,
)
from app.llm.llm_types import LlmMessage, LlmRequest
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tool_registry import ToolRegistry


def test_llm_executor_can_call_model() -> None:
    settings = get_settings()
    executor = LlmExecutor()
    response = executor.complete(
        LlmRequest(
            system_prompt="You are a helpful assistant.",
            context_prompt="",
            messages=[LlmMessage(role="user", content="Say hello in one short sentence.")],
            tools=[],
            tool_choice=None,
            model=settings.test_model or "",
        )
    )

    assert response.content


def test_executor_factory_selects_framework_executor() -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
            executor_policy={"kind": "framework_cli", "framework": "claude"},
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={"kind": "framework_cli", "framework": "claude"},
        tool_registry=ToolRegistry(),
    )

    executor = AgentExecutorFactory().resolve(runtime)

    assert isinstance(executor, FrameworkCliExecutor)


def test_resolve_framework_adapter_selects_known_adapters() -> None:
    assert isinstance(resolve_framework_adapter("claude"), ClaudeCodeAdapter)
    assert isinstance(resolve_framework_adapter("opencode"), OpenCodeAdapter)
    assert isinstance(resolve_framework_adapter("codex"), CodexCliAdapter)


def test_framework_executor_parses_json_output(monkeypatch) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={
            "kind": "framework_cli",
            "framework": "claude",
            "framework_options": {"allowed_tools": ["Read", "Edit"]},
        },
        tool_registry=ToolRegistry(),
    )

    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout='{"content":"framework done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "posix")
    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    response = FrameworkCliExecutor().execute(
        runtime,
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert response.content == "framework done"
    assert response.raw["content"] == "framework done"


def test_claude_adapter_defaults_allowed_tools_when_framework_options_missing(monkeypatch) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={
            "kind": "framework_cli",
            "framework": "claude",
            "framework_options": {},
        },
        tool_registry=ToolRegistry(),
    )
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args[0]
        return SimpleNamespace(stdout='{"content":"framework done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "posix")
    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    FrameworkCliExecutor().execute(
        runtime,
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert "--allowedTools" in captured["args"]
    assert "Read,Edit,Bash,Write" in captured["args"]


def test_framework_executor_reuses_local_env_and_timeout(monkeypatch) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={
            "kind": "framework_cli",
            "framework": "claude",
            "framework_options": {"allowed_tools": ["Read", "Edit"]},
            "timeout_seconds": 123,
        },
        tool_registry=ToolRegistry(),
    )
    captured = {}
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("CLAUDE_TEST_MARKER", "enabled")

    def fake_run(*args, **kwargs):
        captured["env"] = kwargs["env"]
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(stdout='{"content":"framework done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "posix")
    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    response = FrameworkCliExecutor().execute(
        runtime,
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert response.content == "framework done"
    assert captured["env"]["CLAUDE_TEST_MARKER"] == "enabled"
    assert "ANTHROPIC_API_KEY" not in captured["env"]
    assert captured["timeout"] == 123


def test_framework_executor_passes_permission_flags(monkeypatch) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={
            "kind": "framework_cli",
            "framework": "claude",
            "framework_options": {
                "allowed_tools": ["Read", "Edit", "Bash", "Write"],
                "permission_mode": "bypassPermissions",
                "allow_dangerously_skip_permissions": True,
                "dangerously_skip_permissions": True,
            },
        },
        tool_registry=ToolRegistry(),
    )
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args[0]
        return SimpleNamespace(stdout='{"content":"framework done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "posix")
    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    FrameworkCliExecutor().execute(
        runtime,
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert "--allowedTools" in captured["args"]
    assert "Read,Edit,Bash,Write" in captured["args"]
    assert "--permission-mode" in captured["args"]
    assert "bypassPermissions" in captured["args"]
    assert "--allow-dangerously-skip-permissions" in captured["args"]
    assert "--dangerously-skip-permissions" in captured["args"]


def test_framework_executor_uses_runtime_workspace_as_default_cwd(monkeypatch) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={
            "kind": "framework_cli",
            "framework": "claude",
            "framework_options": {"allowed_tools": ["Read", "Edit"]},
        },
        tool_registry=ToolRegistry(),
    )
    captured = {}

    def fake_run(*args, **kwargs):
        captured["cwd"] = kwargs["cwd"]
        return SimpleNamespace(stdout='{"content":"framework done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "posix")
    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    FrameworkCliExecutor().execute(
        runtime,
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert captured["cwd"] == "E:/workspace"


def test_framework_executor_uses_powershell_wrapper_for_windows_claude(monkeypatch) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={
            "kind": "framework_cli",
            "framework": "claude",
            "framework_options": {"allowed_tools": ["Read", "Edit"]},
        },
        tool_registry=ToolRegistry(),
    )
    captured = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args[0]
        captured["env"] = kwargs["env"]
        return SimpleNamespace(stdout='{"content":"framework done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "nt")
    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)

    FrameworkCliExecutor().execute(
        runtime,
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert captured["args"][0] == "powershell"
    assert captured["args"][1] == "-NoProfile"
    assert captured["args"][2] == "-Command"
    assert "claude -p $env:CLAUDE_PROMPT" in captured["args"][3]
    assert "--allowedTools Read,Edit" in captured["args"][3]
    assert captured["env"]["CLAUDE_PROMPT"] == "hello"


def test_framework_executor_delegates_to_adapter(monkeypatch) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Framework Worker",
            agent_kind="worker",
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_profile="framework_worker",
        prompt_plan={"system_profile": "framework_worker"},
        tool_plan={"model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy={"kind": "framework_cli", "framework": "claude"},
        tool_registry=ToolRegistry(),
    )
    captured = {}

    class FakeAdapter:
        def build_command(self, runtime, request, env):
            captured["build_runtime"] = runtime
            captured["build_request"] = request
            env = dict(env)
            env["FAKE"] = "1"
            return ["fake-cli", "--json"], env

        def parse_response(self, completed):
            captured["completed"] = completed
            return SimpleNamespace(content="adapter done", raw={"ok": True})

    def fake_run(*args, **kwargs):
        captured["args"] = args[0]
        captured["env"] = kwargs["env"]
        return SimpleNamespace(stdout='{"content":"ignored"}', stderr="", returncode=0)

    monkeypatch.setattr("app.llm.llm_executor.subprocess.run", fake_run)
    monkeypatch.setattr("app.llm.llm_executor.resolve_framework_adapter", lambda framework: FakeAdapter())

    response = FrameworkCliExecutor().execute(
        runtime,
        LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert response.content == "adapter done"
    assert captured["args"] == ["fake-cli", "--json"]
    assert captured["env"]["FAKE"] == "1"
