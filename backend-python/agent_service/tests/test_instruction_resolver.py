from uuid import uuid4

from agent_service.app.models.agent import AgentModel
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.runtime.instruction.instruction_resolver import InstructionResolver
from agent_service.app.runtime.runtime_assembler import RuntimeBundle


def _build_runtime_bundle(workspace_root: str, executor_config: dict | None = None) -> RuntimeBundle:
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
            executor_config=executor_config or {"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
        ),
        workspace_root=workspace_root,
        role="worker",
        prompt_policy={"system_profile": "worker"},
        tool_config=tool_config,
        executor_config=executor_config or {"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
        skill_config={"builtins_enabled": True, "paths": [], "include_global": False, "allowed_skills": []},
        mcp_config={"enabled": False, "servers": []},
        skill_registry=None,
        mcp_runtime={"enabled": False, "tools": []},
    )


def test_instruction_resolver_reads_agents_file_by_default(tmp_path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "AGENTS.md").write_text("project instructions", encoding="utf-8")

    view = InstructionResolver().resolve(_build_runtime_bundle(str(workspace_root)))

    assert [item.content for item in view.items] == ["project instructions"]


def test_instruction_resolver_reads_claude_file_for_claude_framework(tmp_path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "AGENTS.md").write_text("agents instructions", encoding="utf-8")
    (workspace_root / "CLAUDE.md").write_text("claude instructions", encoding="utf-8")

    view = InstructionResolver().resolve(
        _build_runtime_bundle(
            str(workspace_root),
            executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test", "framework": "claude"},
        )
    )

    assert [item.content for item in view.items] == ["agents instructions", "claude instructions"]
