from uuid import uuid4

from app.llm.llm_types import LlmResponse
from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle


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
    from app.tools.opencode_tool import OpenCodeTool

    runtime_bundle = _runtime_bundle()

    monkeypatch.setattr(
        "app.tools.opencode_tool.ExternalCodeRunner.run",
        lambda self, **kwargs: LlmResponse(content="opencode ok", raw=kwargs),
    )

    result = OpenCodeTool().run(runtime=runtime_bundle, arguments={"prompt": "Rename the function"})

    assert result["status"] == "ok"
    assert result["content"] == "opencode ok"
    assert result["framework"] == "opencode"
