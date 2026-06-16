from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from agent_service.app.models.agent import AgentModel
from agent_service.app.models.agent_run import AgentRunModel
from agent_service.app.runtime.runtime_assembler import RuntimeBundle
from agent_service.app.runtime.tools.tool_registry import ToolRegistry
from agent_service.app.runtime.workspace.workspace_session import WorkspaceSession
from agent_service.app.tools.bash_tool import BashTool


def _runtime(tmp_path: Path, tool_config: dict | None = None) -> RuntimeBundle:
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
        tool_config=tool_config
        or {
            "tools": [{"name": "bash_tool", "enabled": True, "options": {}}],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
            "command_policies": {"bash": {"*": "allow"}},
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
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
        tool_config={
            "tools": [{"name": "bash_tool", "enabled": True, "options": {}}],
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
        tool_config={
            "tools": [{"name": "bash_tool", "enabled": True, "options": {}}],
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


def test_bash_tool_reports_success_when_command_has_no_stdout(tmp_path: Path) -> None:
    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": (
                'python -c "from pathlib import Path; '
                "Path('created.txt').write_text('ok', encoding='utf-8')\""
            ),
            "description": "Creates a file",
        },
    )

    assert result["metadata"]["exit_code"] == 0
    assert (tmp_path / "created.txt").exists()
    assert "completed successfully" in result["output"].lower()
    assert "no output" in result["output"].lower()


def test_bash_tool_handles_non_utf8_output_without_strip_failure(tmp_path: Path, monkeypatch) -> None:
    tool = BashTool()
    runtime = _runtime(tmp_path)

    class _FakeProcess:
        returncode = 0
        pid = 4321

        def communicate(self):
            return None, None

        def poll(self):
            return 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(
        "agent_service.app.tools.bash_tool.subprocess.Popen",
        lambda *args, **kwargs: _FakeProcess(),
    )

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": "Test-Path .",
            "description": "Checks current directory",
        },
    )

    assert "completed successfully" in result["output"].lower()
    assert "no output" in result["output"].lower()
    assert result["metadata"]["exit_code"] == 0


def test_bash_tool_does_not_hang_on_command_reading_stdin(tmp_path: Path) -> None:
    # A script that reads stdin must not block forever: stdin is closed
    # (DEVNULL), so input() gets EOF and the process exits promptly instead of
    # freezing the whole run. Generous timeout proves we exit via EOF, not timeout.
    script = tmp_path / "reads_stdin.py"
    script.write_text(
        "try:\n"
        "    data = input()\n"
        "    print('got', data)\n"
        "except EOFError:\n"
        "    print('eof')\n",
        encoding="utf-8",
    )

    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": "python reads_stdin.py",
            "description": "Reads stdin",
            "timeout": 30000,
        },
    )

    assert result["metadata"]["timed_out"] is False
    assert result["metadata"]["exit_code"] == 0
    assert "eof" in result["output"]


def test_bash_tool_aborts_running_command_when_cancel_event_fires(tmp_path: Path) -> None:
    # 抢占式打断：命令执行中途置位 cancel_event，必须立刻杀进程并返回 aborted，
    # 而不是等命令自然跑完（这里是 10s sleep，但应在 ~1s 内被打断）。
    import threading
    import time

    cancel_event = threading.Event()
    runtime = _runtime(tmp_path)
    runtime.cancel_event = cancel_event

    # 0.5s 后从另一线程触发打断
    threading.Timer(0.5, cancel_event.set).start()

    tool = BashTool()
    started = time.monotonic()
    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": 'python -c "import time; time.sleep(10)"',
            "description": "Sleeps long",
            "timeout": 30000,
        },
    )
    elapsed = time.monotonic() - started

    assert result["metadata"]["aborted"] is True
    assert result["metadata"]["timed_out"] is False
    assert elapsed < 5, f"打断应在数秒内生效，实际 {elapsed:.1f}s"
    assert "aborted" in result["output"].lower()


def test_bash_tool_aborts_problematic_powershell_heredoc_command(tmp_path: Path) -> None:
    import threading
    import time

    cancel_event = threading.Event()
    runtime = _runtime(tmp_path)
    runtime.cancel_event = cancel_event

    threading.Timer(0.5, cancel_event.set).start()

    tool = BashTool()
    started = time.monotonic()
    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": (
                "Set-Content -Path add.py -Value @'\n"
                "#!/usr/bin/env python3\n"
                "# -*- coding: utf-8 -*-\n\n"
                "def add(a, b):\n"
                "    return a + b\n\n"
                'if __name__ == \"__main__\":\n'
                "    a = 5\n"
                "    b = 3\n"
                "    result = add(a, b)\n"
                '    print(f\"{a} + {b} = {result}\")\n'
                "'@ -Encoding UTF8"
            ),
            "description": "Creates add.py via PowerShell heredoc",
            "timeout": 30000,
        },
    )
    elapsed = time.monotonic() - started

    assert result["metadata"]["aborted"] is True
    assert elapsed < 5, f"problematic PowerShell command should abort quickly, got {elapsed:.1f}s"
