from types import SimpleNamespace
from uuid import uuid4

from app.config import get_settings
from app.llm.framework_adapters.claude_code_adapter import ClaudeCodeAdapter
from app.llm.framework_adapters.codex_cli_adapter import CodexCliAdapter
from app.llm.framework_adapters.opencode_adapter import OpenCodeAdapter
from app.llm.llm_executor import AgentExecutorFactory, InternalLlmExecutor, LlmExecutor, resolve_framework_adapter
from app.llm.llm_types import LlmMessage, LlmRequest
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle


def _runtime_bundle() -> RuntimeBundle:
    tool_config = {
        "tools": [{"name": "code_tool", "enabled": True, "options": {}}],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }
    return RuntimeBundle(
        agent_run=AgentRunModel(
            run_id=uuid4(),
            agent_id=uuid4(),
            agent_kind="worker",
            workspace_id=uuid4(),
        ),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Worker",
            agent_kind="worker",
            tool_config=tool_config,
            executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_policy={"system_profile": "worker"},
        tool_config=tool_config,
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )


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


def test_executor_factory_always_selects_internal_executor() -> None:
    executor = AgentExecutorFactory().resolve(_runtime_bundle())

    assert isinstance(executor, InternalLlmExecutor)


def test_resolve_framework_adapter_selects_known_adapters() -> None:
    assert isinstance(resolve_framework_adapter("claude"), ClaudeCodeAdapter)
    assert isinstance(resolve_framework_adapter("opencode"), OpenCodeAdapter)
    assert isinstance(resolve_framework_adapter("codex"), CodexCliAdapter)


def test_claude_adapter_build_prompt_includes_system_and_context() -> None:
    runtime = _runtime_bundle()

    prompt = ClaudeCodeAdapter().build_prompt(
        runtime,
        LlmRequest(
            system_prompt="[ENVIRONMENT]\nworkspace_root=E:/workspace",
            context_prompt="[RUNTIME_CONTEXT]\nrun_id=123",
            messages=[LlmMessage(role="user", content="hello")],
        ),
    )

    assert "[ENVIRONMENT]" in prompt
    assert "workspace_root=E:/workspace" in prompt
    assert "[RUNTIME_CONTEXT]" in prompt
    assert "[USER_MESSAGE]" in prompt
    assert "hello" in prompt


def test_claude_adapter_uses_explicit_tool_options(monkeypatch) -> None:
    runtime = _runtime_bundle()
    captured = {}

    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "posix")

    command_args, _env = ClaudeCodeAdapter().build_command(
        runtime=runtime,
        request=LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello")],
        ),
        env={},
        options={
            "command": "claude",
            "allowed_tools": ["Read", "Edit", "Bash", "Write"],
            "permission_mode": "bypassPermissions",
            "allow_dangerously_skip_permissions": True,
            "dangerously_skip_permissions": True,
        },
    )
    captured["args"] = command_args

    assert "--allowedTools" in captured["args"]
    assert "Read,Edit,Bash,Write" in captured["args"]
    assert "--permission-mode" in captured["args"]
    assert "bypassPermissions" in captured["args"]
    assert "--allow-dangerously-skip-permissions" in captured["args"]
    assert "--dangerously-skip-permissions" in captured["args"]


def test_opencode_adapter_builds_run_command_and_parses_event_stream(monkeypatch) -> None:
    runtime = _runtime_bundle()
    captured = {}

    event_stream = "\n".join(
        [
            '{"type":"step_start"}',
            '{"type":"text","part":{"type":"text","text":"intermediate"}}',
            '{"type":"text","part":{"type":"text","text":"final result"}}',
        ]
    )

    monkeypatch.setattr("app.llm.framework_adapters.opencode_adapter.os.name", "posix")

    command_args, _env = OpenCodeAdapter().build_command(
        runtime=runtime,
        request=LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello opencode")],
        ),
        env={},
        options={"command": "opencode", "dangerously_skip_permissions": True},
    )
    captured["args"] = command_args

    response = OpenCodeAdapter().parse_response(SimpleNamespace(stdout=event_stream, stderr="", returncode=0))

    assert captured["args"][1] == "run"
    assert "--format" in captured["args"]
    assert captured["args"][4] == "json"
    assert "--dangerously-skip-permissions" in captured["args"]
    assert response.content == "final result"
    assert len(response.raw["events"]) == 3
    assert "system" in captured["args"][2]
    assert "context" in captured["args"][2]
    assert "[USER_MESSAGE] hello opencode" in captured["args"][2]


def test_opencode_adapter_prefers_cmd_entrypoint_on_windows(monkeypatch) -> None:
    runtime = _runtime_bundle()

    monkeypatch.setattr("app.llm.framework_adapters.opencode_adapter.os.name", "nt")
    monkeypatch.setattr(
        "app.llm.framework_adapters.opencode_adapter.shutil.which",
        lambda candidate: f"C:/tools/{candidate}" if candidate == "opencode.cmd" else None,
    )

    command_args, _env = OpenCodeAdapter().build_command(
        runtime=runtime,
        request=LlmRequest(
            system_prompt="system",
            context_prompt="context",
            messages=[LlmMessage(role="user", content="hello opencode")],
        ),
        env={},
        options={"command": "opencode", "dangerously_skip_permissions": True},
    )

    assert command_args[0] == "C:/tools/opencode.cmd"
    assert command_args[1] == "run"
    assert command_args[3:5] == ["--format", "json"]
    assert "--dangerously-skip-permissions" in command_args
    assert "system" in command_args[2]
    assert "context" in command_args[2]
    assert "[USER_MESSAGE] hello opencode" in command_args[2]
