from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.instruction.instruction_resolver import InstructionResolver


def _build_runtime_bundle(workspace_root: str, executor_policy: dict | None = None) -> RuntimeBundle:
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
        ),
        workspace_root=workspace_root,
        role="worker",
        prompt_policy={"system_profile": "framework_worker"},
        tool_policy={"system_toolset": "none", "model_tools_enabled": False, "runtime_tools_enabled": False},
        executor_policy=executor_policy or {"kind": "internal_llm"},
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
            executor_policy={"kind": "framework_cli", "framework": "claude"},
        )
    )

    assert [item.content for item in view.items] == ["agents instructions", "claude instructions"]
