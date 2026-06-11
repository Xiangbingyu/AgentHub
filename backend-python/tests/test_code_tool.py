from pathlib import Path
from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_registry import ToolRegistry
from app.runtime.workspace.workspace_session import WorkspaceSession
from app.tools.code_tool import CodeTool


def test_code_tool_writes_workspace_file(tmp_path: Path) -> None:
    runtime = RuntimeBundle(
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
        ),
        workspace_root=str(tmp_path),
        role="worker",
        prompt_policy={"system_profile": "worker"},
        tool_config={
            "tools": [{"name": "code_tool", "enabled": True, "options": {}}],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
        tool_registry=ToolRegistry(),
        workspace_session=WorkspaceSession(str(tmp_path)),
    )

    tool = CodeTool()
    response = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "action": "write_file",
            "path": "src/example.py",
            "content": "print('hello')",
        },
    )

    assert (tmp_path / "src" / "example.py").read_text(encoding="utf-8") == "print('hello')"
    assert response["status"] == "ok"
