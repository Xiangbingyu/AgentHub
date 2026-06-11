from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle


def _runtime_bundle() -> RuntimeBundle:
    tool_config = {
        "tools": [
            {"name": "claude_code_tool", "enabled": True, "options": {"command": "claude", "timeout_seconds": 90}}
        ],
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


def test_claude_code_tool_uses_agent_tool_options(monkeypatch) -> None:
    from app.tools.claude_code_tool import ClaudeCodeTool

    runtime_bundle = _runtime_bundle()
    captured = {}

    def fake_run(*args, **kwargs):
        captured["command"] = args[0]
        captured["cwd"] = kwargs["cwd"]
        captured["timeout"] = kwargs["timeout"]
        return type("Completed", (), {"stdout": '{"content":"tool ok"}', "stderr": "", "returncode": 0})()

    monkeypatch.setattr("app.tools.claude_code_tool.subprocess.run", fake_run)
    monkeypatch.setattr("app.tools.framework_adapters.claude_code_adapter.os.name", "posix")

    result = ClaudeCodeTool().run(runtime=runtime_bundle, arguments={"prompt": "Refactor app.py"})

    assert result["status"] == "ok"
    assert result["content"] == "tool ok"
    assert result["framework"] == "claude"
    assert captured["cwd"] == runtime_bundle.workspace_root
    assert captured["timeout"] == 90


def test_claude_code_tool_forces_utf8_subprocess_decoding_on_windows(monkeypatch) -> None:
    from app.tools.claude_code_tool import ClaudeCodeTool

    runtime_bundle = _runtime_bundle()
    captured = {}

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return type("Completed", (), {"stdout": '{"content":"tool ok"}', "stderr": "", "returncode": 0})()

    monkeypatch.setattr("app.tools.claude_code_tool.subprocess.run", fake_run)
    monkeypatch.setattr("app.tools.framework_adapters.claude_code_adapter.os.name", "nt")

    result = ClaudeCodeTool().run(runtime=runtime_bundle, arguments={"prompt": "Refactor app.py"})

    assert result["status"] == "ok"
    assert "text" not in captured
    assert "encoding" not in captured
    assert "errors" not in captured


def test_claude_code_tool_decodes_byte_output_with_utf8_replacement(monkeypatch) -> None:
    from app.tools.claude_code_tool import ClaudeCodeTool

    runtime_bundle = _runtime_bundle()

    def fake_run(*args, **kwargs):
        return type(
            "Completed",
            (),
            {
                "stdout": b'{"content":"tool ok"}\x80',
                "stderr": b"",
                "returncode": 0,
            },
        )()

    monkeypatch.setattr("app.tools.claude_code_tool.subprocess.run", fake_run)
    monkeypatch.setattr("app.tools.framework_adapters.claude_code_adapter.os.name", "posix")

    result = ClaudeCodeTool().run(runtime=runtime_bundle, arguments={"prompt": "Refactor app.py"})

    assert result["status"] == "ok"
    assert "tool ok" in result["content"]
