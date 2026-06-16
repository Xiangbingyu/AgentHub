from uuid import uuid4

from agent_service.app.models.agent import AgentModel
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.runtime.runtime_assembler import RuntimeBundle


def _runtime_bundle() -> RuntimeBundle:
    tool_config = {
        "tools": [{"name": "opencode_tool", "enabled": True, "options": {"command": "opencode", "timeout_seconds": 60}}],
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


def test_opencode_tool_uses_agent_tool_options(monkeypatch) -> None:
    from agent_service.app.tools.opencode_tool import OpenCodeTool

    runtime_bundle = _runtime_bundle()
    captured = {}

    def fake_run(*args, **kwargs):
        captured["command"] = args[0]
        captured["cwd"] = kwargs["cwd"]
        captured["timeout"] = kwargs["timeout"]
        return type("Completed", (), {"stdout": '{"type":"text","part":{"type":"text","text":"opencode ok"}}', "stderr": "", "returncode": 0})()

    monkeypatch.setattr("agent_service.app.tools.opencode_tool.subprocess.run", fake_run)
    monkeypatch.setattr("agent_service.app.tools.framework_adapters.opencode_adapter.os.name", "posix")

    result = OpenCodeTool().run(runtime=runtime_bundle, arguments={"prompt": "Rename the function"})

    assert result["status"] == "ok"
    assert result["content"] == "opencode ok"
    assert result["framework"] == "opencode"
    assert captured["cwd"] == runtime_bundle.workspace_root
    assert captured["timeout"] == 60
    assert "text" not in captured
    assert "encoding" not in captured
    assert "errors" not in captured
