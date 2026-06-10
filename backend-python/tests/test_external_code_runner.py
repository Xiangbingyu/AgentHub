from types import SimpleNamespace
from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle


def _runtime_bundle() -> RuntimeBundle:
    tool_config = {
        "tools": [{"name": "claude_code_tool", "enabled": True, "options": {"command": "claude", "timeout_seconds": 90}}],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": False,
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


def test_external_code_runner_executes_claude_adapter(monkeypatch) -> None:
    from app.tools.external_code_runner import ExternalCodeRunner

    runtime = _runtime_bundle()
    captured = {}

    def fake_run(*args, **kwargs):
        captured["command"] = args[0]
        captured["cwd"] = kwargs["cwd"]
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(stdout='{"content":"done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.tools.external_code_runner.subprocess.run", fake_run)
    monkeypatch.setattr("app.llm.framework_adapters.claude_code_adapter.os.name", "posix")

    response = ExternalCodeRunner().run(
        runtime=runtime,
        framework="claude",
        tool_options={"command": "claude", "timeout_seconds": 90, "allowed_tools": ["Read", "Edit"]},
        prompt="Update the file",
    )

    assert response.content == "done"
    assert captured["cwd"] == runtime.workspace_root
    assert captured["timeout"] == 90
    assert captured["command"][0].lower().endswith("claude") or captured["command"][0].lower().endswith("claude.cmd")
