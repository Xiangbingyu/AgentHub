from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_registry import ToolRegistry
from app.runtime.workspace.workspace_session import WorkspaceSession
from app.tools.bash_tool import BashTool


def _runtime(tmp_path: Path, tool_policy: dict | None = None) -> RuntimeBundle:
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
        workspace_root=str(tmp_path),
        role="worker",
        prompt_policy={"system_profile": "worker"},
        tool_policy=tool_policy
        or {
            "system_toolset": "worker_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
            "command_policies": {"bash": {"*": "allow"}},
        },
        executor_policy={"kind": "internal_llm"},
        tool_registry=ToolRegistry(),
        workspace_session=WorkspaceSession(str(tmp_path)),
    )


def test_bash_tool_executes_command_in_workspace_root(tmp_path: Path) -> None:
    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": 'python -c "print(\'hello bash tool\')"',
            "description": "Prints a greeting",
        },
    )

    assert result["title"] == "Prints a greeting"
    assert "hello bash tool" in result["output"]
    assert result["metadata"]["exit_code"] == 0
    assert result["metadata"]["timed_out"] is False
    assert result["metadata"]["aborted"] is False
    assert result["metadata"]["truncated"] is False
    assert Path(result["metadata"]["cwd"]) == tmp_path


def test_bash_tool_resolves_relative_workdir_inside_workspace(tmp_path: Path) -> None:
    (tmp_path / "subdir").mkdir()
    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": 'python -c "import os; print(os.getcwd())"',
            "description": "Prints cwd",
            "workdir": "subdir",
        },
    )

    assert result["metadata"]["exit_code"] == 0
    assert Path(result["metadata"]["cwd"]) == tmp_path / "subdir"
    assert str(tmp_path / "subdir") in result["output"]


def test_bash_tool_rejects_workdir_outside_workspace(tmp_path: Path) -> None:
    outside = tmp_path.parent
    tool = BashTool()
    runtime = _runtime(tmp_path)

    try:
        tool.run(
            run_id=runtime.agent_run.run_id,
            workspace_id=runtime.agent_run.workspace_id,
            runtime=runtime,
            arguments={
                "command": 'python -c "print(\'blocked\')"',
                "description": "Should be rejected",
                "workdir": str(outside),
            },
        )
    except ValueError as exc:
        assert "workdir escapes workspace root" in str(exc)
    else:
        raise AssertionError("expected bash_tool to reject out-of-workspace workdir")


def test_bash_tool_denies_command_when_prefix_rule_blocks_it(tmp_path: Path) -> None:
    tool = BashTool()
    runtime = _runtime(
        tmp_path,
        tool_policy={
            "system_toolset": "worker_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
            "command_policies": {
                "bash": {
                    "*": "allow",
                    "python -c *": "deny",
                }
            },
        },
    )

    try:
        tool.run(
            run_id=runtime.agent_run.run_id,
            workspace_id=runtime.agent_run.workspace_id,
            runtime=runtime,
            arguments={
                "command": 'python -c "print(\'denied\')"',
                "description": "Denied command",
            },
        )
    except ValueError as exc:
        assert "bash command denied by policy" in str(exc)
    else:
        raise AssertionError("expected bash_tool to reject denied command")


def test_bash_tool_denies_multi_command_input_if_any_segment_is_denied(tmp_path: Path) -> None:
    tool = BashTool()
    runtime = _runtime(
        tmp_path,
        tool_policy={
            "system_toolset": "worker_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
            "command_policies": {
                "bash": {
                    "*": "allow",
                    "python -c *": "deny",
                }
            },
        },
    )

    try:
        tool.run(
            run_id=runtime.agent_run.run_id,
            workspace_id=runtime.agent_run.workspace_id,
            runtime=runtime,
            arguments={
                "command": 'echo safe && python -c "print(\'blocked\')"',
                "description": "Mixed commands",
            },
        )
    except ValueError as exc:
        assert "bash command denied by policy" in str(exc)
    else:
        raise AssertionError("expected denied command segment to block execution")


def test_bash_tool_returns_timeout_metadata_when_command_expires(tmp_path: Path) -> None:
    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": 'python -c "import time; time.sleep(1)"',
            "description": "Sleeps briefly",
            "timeout": 10,
        },
    )

    assert result["metadata"]["exit_code"] is None
    assert result["metadata"]["timed_out"] is True
    assert result["metadata"]["aborted"] is False
    assert "timed out" in result["output"].lower()


def test_bash_tool_truncates_large_output(tmp_path: Path) -> None:
    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": 'python -c "print(\'a\' * 20000)"',
            "description": "Prints large output",
        },
    )

    assert result["metadata"]["truncated"] is True
    assert "...output truncated..." in result["output"]


def test_bash_tool_moves_file_with_powershell_command(tmp_path: Path) -> None:
    source_path = tmp_path / "test1" / "bash_tool_test1.md"
    target_path = tmp_path / "test2" / "bash_tool_test1.md"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("test\n", encoding="utf-8")

    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": f'Move-Item -LiteralPath "{source_path}" -Destination "{target_path}"',
            "description": "Moves test file",
        },
    )

    assert result["metadata"]["exit_code"] == 0
    assert not source_path.exists()
    assert target_path.exists()
    assert target_path.read_text(encoding="utf-8").strip() == "test"
