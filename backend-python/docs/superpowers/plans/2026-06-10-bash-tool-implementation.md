# Bash Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a runtime-visible `bash_tool` that executes commands inside the session workspace, enforces command-pattern policy checks through the existing runtime tool policy system, and returns structured command results with timeout and truncation metadata.

**Architecture:** Keep `bash_tool` as a normal worker runtime tool alongside `code_tool`. Add a lightweight preflight layer inside the tool to validate `workdir`, derive command-prefix patterns, and ask the runtime policy layer whether execution is allowed before launching a subprocess. Extend the current tool policy shape just enough to support pattern-based `bash` rules without introducing a second permission subsystem.

**Tech Stack:** Python 3.13, pytest, Pydantic, existing runtime/tool registry architecture, standard library subprocess

---

## File Map

- Create: `app/schemas/bash_tool.py`
  - Defines the Pydantic request model and model-visible tool definition for `bash_tool`.
- Create: `app/tools/bash_tool.py`
  - Implements input validation, workspace-contained `workdir` resolution, command pattern extraction, policy evaluation, subprocess execution, timeout handling, and output truncation.
- Modify: `app/runtime/policy/tool_policy_resolver.py`
  - Extends default worker tool policy to carry `bash` rule configuration and preserves existing framework disabling behavior.
- Modify: `app/runtime/tools/tool_resolver.py`
  - Registers `bash_tool` in `worker_default` alongside `code_tool`.
- Create: `tests/test_bash_tool.py`
  - Covers `bash_tool` execution, policy checks, `workdir` containment, timeout handling, and truncation.
- Modify: `tests/test_tool_resolver.py`
  - Verifies worker tool visibility includes `bash_tool`.
- Modify: `tests/test_runtime_policy_resolvers.py`
  - Verifies default policy shape and framework-worker disabling still behave correctly.

### Task 1: Add `bash_tool` schema and worker tool registration tests

**Files:**
- Create: `app/schemas/bash_tool.py`
- Modify: `app/runtime/tools/tool_resolver.py`
- Modify: `tests/test_tool_resolver.py`
- Test: `tests/test_tool_resolver.py`

- [ ] **Step 1: Write the failing worker tool visibility test**

Add this test to `tests/test_tool_resolver.py`:

```python
def test_tool_resolver_builds_worker_code_and_bash_tool_view() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_policy={
            "system_toolset": "worker_default",
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_policy={"kind": "internal_llm"},
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert [item.name for item in view.system_tools] == ["code_tool", "bash_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["code_tool", "bash_tool"]
    assert view.tool_choice == "auto"
    assert "code_tool" in runtime.tool_registry.tools
    assert "bash_tool" in runtime.tool_registry.tools
```

- [ ] **Step 2: Run the resolver test to verify it fails**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_tool_resolver.py::test_tool_resolver_builds_worker_code_and_bash_tool_view -v`
Expected: FAIL because `bash_tool` is not registered and not present in `model_tools`.

- [ ] **Step 3: Add the `bash_tool` request schema and definition builder**

Create `app/schemas/bash_tool.py` with:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class BashToolRequest(BaseModel):
    command: str = Field(min_length=1)
    description: str = Field(min_length=1)
    timeout: int | None = Field(default=None, gt=0)
    workdir: str | None = None


def build_bash_tool_definition() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "bash_tool",
            "description": "Execute a shell command inside the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute."},
                    "description": {"type": "string", "description": "Short description of what the command does."},
                    "timeout": {
                        "type": "integer",
                        "description": "Optional timeout in milliseconds.",
                        "minimum": 1,
                    },
                    "workdir": {
                        "type": "string",
                        "description": "Optional working directory relative to the workspace root.",
                    },
                },
                "required": ["command", "description"],
                "additionalProperties": False,
            },
        },
    }
```

- [ ] **Step 4: Register `bash_tool` for `worker_default`**

Update `app/runtime/tools/tool_resolver.py` imports and worker registration block to:

```python
from app.schemas.bash_tool import BashToolRequest, build_bash_tool_definition
from app.tools.bash_tool import BashTool
```

and inside `if system_toolset == "worker_default":`

```python
            registry.register(
                ToolSpec(
                    name="bash_tool",
                    tool=BashTool(),
                    definition=build_bash_tool_definition(),
                    request_model=BashToolRequest,
                    invoke=default_invoke,
                )
            )
```

Also create a temporary stub `app/tools/bash_tool.py` so imports resolve:

```python
from __future__ import annotations


class BashTool:
    def run(self, **_kwargs):
        raise NotImplementedError("bash_tool is not implemented yet")
```

- [ ] **Step 5: Run the resolver test to verify it passes**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_tool_resolver.py::test_tool_resolver_builds_worker_code_and_bash_tool_view -v`
Expected: PASS

- [ ] **Step 6: Commit the schema and registration foundation**

```bash
git add app/schemas/bash_tool.py app/tools/bash_tool.py app/runtime/tools/tool_resolver.py tests/test_tool_resolver.py
git commit -m "feat(runtime): expose bash tool to workers"
```

### Task 2: Extend tool policy defaults for `bash` pattern rules

**Files:**
- Modify: `app/runtime/policy/tool_policy_resolver.py`
- Modify: `tests/test_runtime_policy_resolvers.py`
- Test: `tests/test_runtime_policy_resolvers.py`

- [ ] **Step 1: Write the failing tool policy defaults test**

Add these tests to `tests/test_runtime_policy_resolvers.py`:

```python
def test_tool_policy_resolver_includes_default_bash_policy_rules() -> None:
    tool_policy = ToolPolicyResolver().resolve(
        {"tool_policy": {}},
        role="worker",
        executor_policy={"kind": "internal_llm"},
    )

    assert tool_policy["command_policies"] == {"bash": {"*": "allow"}}


def test_tool_policy_resolver_preserves_runtime_snapshot_command_policies() -> None:
    tool_policy = ToolPolicyResolver().resolve(
        {
            "tool_policy": {
                "command_policies": {
                    "bash": {
                        "*": "deny",
                        "git status *": "allow",
                    }
                }
            }
        },
        role="worker",
        executor_policy={"kind": "internal_llm"},
    )

    assert tool_policy["command_policies"] == {
        "bash": {
            "*": "deny",
            "git status *": "allow",
        }
    }
```

- [ ] **Step 2: Run the policy tests to verify they fail**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py::test_tool_policy_resolver_includes_default_bash_policy_rules tests/test_runtime_policy_resolvers.py::test_tool_policy_resolver_preserves_runtime_snapshot_command_policies -v`
Expected: FAIL because `command_policies` is not present.

- [ ] **Step 3: Extend the default tool policy shape**

Update `app/runtime/policy/tool_policy_resolver.py` default policy block to:

```python
        tool_policy = {
            "system_toolset": default_toolset,
            "user_tools": [],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
            "command_policies": {
                "bash": {
                    "*": "allow",
                }
            },
        }
```

Keep the existing `tool_policy.update(runtime_snapshot.get("tool_policy", {}))` behavior so caller-provided command rules replace defaults cleanly.

- [ ] **Step 4: Preserve framework worker disabling behavior**

Keep this block unchanged in behavior:

```python
        if executor_kind != "internal_llm":
            tool_policy["system_toolset"] = "none"
            tool_policy["model_tools_enabled"] = False
            tool_policy["runtime_tools_enabled"] = False
            tool_policy["auto_tool_choice"] = False
```

No extra `command_policies` mutation is required for framework executors; they simply cannot access runtime tools.

- [ ] **Step 5: Run the policy resolver tests to verify they pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py -v`
Expected: PASS

- [ ] **Step 6: Commit the policy shape change**

```bash
git add app/runtime/policy/tool_policy_resolver.py tests/test_runtime_policy_resolvers.py
git commit -m "feat(runtime): add bash command policy defaults"
```

### Task 3: Implement `bash_tool` preflight and successful execution path

**Files:**
- Modify: `app/tools/bash_tool.py`
- Create: `tests/test_bash_tool.py`
- Test: `tests/test_bash_tool.py`

- [ ] **Step 1: Write the failing execution and workdir tests**

Create `tests/test_bash_tool.py` with:

```python
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
            "command": "python -c \"print('hello bash tool')\"",
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
            "command": "python -c \"import os; print(os.getcwd())\"",
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
                "command": "python -c \"print('blocked')\"",
                "description": "Should be rejected",
                "workdir": str(outside),
            },
        )
    except ValueError as exc:
        assert "workdir escapes workspace root" in str(exc)
    else:
        raise AssertionError("expected bash_tool to reject out-of-workspace workdir")
```

- [ ] **Step 2: Run the new bash tool tests to verify they fail**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_bash_tool.py -v`
Expected: FAIL because `BashTool` is only a stub.

- [ ] **Step 3: Implement minimal `bash_tool` request parsing, workdir resolution, and successful execution**

Replace `app/tools/bash_tool.py` with:

```python
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from app.schemas.bash_tool import BashToolRequest


class BashTool:
    DEFAULT_TIMEOUT_MS = 120000
    MAX_OUTPUT_CHARS = 12000

    def run(self, *, runtime, arguments: BashToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, BashToolRequest) else BashToolRequest.model_validate(arguments)
        cwd = self._resolve_workdir(runtime.workspace_root, request.workdir)
        self._check_policy(runtime.tool_policy, request.command)
        completed = subprocess.run(
            request.command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=(request.timeout or self.DEFAULT_TIMEOUT_MS) / 1000,
        )
        output, truncated = self._truncate_output(completed.stdout, completed.stderr)
        return {
            "title": request.description,
            "output": output,
            "metadata": {
                "exit_code": completed.returncode,
                "timed_out": False,
                "aborted": False,
                "truncated": truncated,
                "cwd": str(cwd),
                "command": request.command,
            },
        }

    def _resolve_workdir(self, workspace_root: str, workdir: str | None) -> Path:
        root = Path(workspace_root).resolve()
        target = root if not workdir else Path(workdir)
        if not target.is_absolute():
            target = (root / target).resolve()
        else:
            target = target.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"workdir escapes workspace root: {workdir}") from exc
        if not target.exists() or not target.is_dir():
            raise ValueError(f"workdir does not exist: {workdir}")
        return target

    def _check_policy(self, tool_policy: dict, command: str) -> None:
        rules = ((tool_policy or {}).get("command_policies") or {}).get("bash") or {"*": "allow"}
        action = rules.get("*")
        if action == "deny":
            raise ValueError(f"bash command denied by policy: {command}")

    def _truncate_output(self, stdout: str, stderr: str) -> tuple[str, bool]:
        output = stdout
        if stderr:
            output = f"{stdout}\n{stderr}" if stdout else stderr
        output = output.strip() or "(no output)"
        if len(output) <= self.MAX_OUTPUT_CHARS:
            return output, False
        return output[: self.MAX_OUTPUT_CHARS] + "\n\n...output truncated...", True
```

- [ ] **Step 4: Run the bash tool tests to verify they pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_bash_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit the execution baseline**

```bash
git add app/tools/bash_tool.py tests/test_bash_tool.py
git commit -m "feat(tools): add bash tool execution baseline"
```

### Task 4: Implement command-prefix preflight and deny rules

**Files:**
- Modify: `app/tools/bash_tool.py`
- Modify: `tests/test_bash_tool.py`
- Test: `tests/test_bash_tool.py`

- [ ] **Step 1: Write the failing policy preflight tests**

Add these tests to `tests/test_bash_tool.py`:

```python
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
                "command": "python -c \"print('denied')\"",
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
                "command": "echo safe && python -c \"print('blocked')\"",
                "description": "Mixed commands",
            },
        )
    except ValueError as exc:
        assert "bash command denied by policy" in str(exc)
    else:
        raise AssertionError("expected denied command segment to block execution")
```

- [ ] **Step 2: Run the policy tests to verify they fail**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_bash_tool.py::test_bash_tool_denies_command_when_prefix_rule_blocks_it tests/test_bash_tool.py::test_bash_tool_denies_multi_command_input_if_any_segment_is_denied -v`
Expected: FAIL because current policy logic only checks the catch-all `*` rule.

- [ ] **Step 3: Implement command-prefix derivation and wildcard matching**

Update `app/tools/bash_tool.py` to add:

```python
import fnmatch
import shlex
```

and replace `_check_policy()` with:

```python
    def _check_policy(self, tool_policy: dict, command: str) -> None:
        rules = ((tool_policy or {}).get("command_policies") or {}).get("bash") or {"*": "allow"}
        for pattern in self._derive_patterns(command):
            action = self._resolve_rule_action(rules, pattern)
            if action == "deny":
                raise ValueError(f"bash command denied by policy: {pattern}")

    def _derive_patterns(self, command: str) -> list[str]:
        parts: list[str] = []
        for segment in self._split_segments(command):
            tokens = self._tokenize(segment)
            if not tokens:
                continue
            if len(tokens) >= 2 and not tokens[1].startswith("-"):
                parts.append(f"{tokens[0]} {tokens[1]} *")
                continue
            parts.append(f"{tokens[0]} *")
        return parts or [command.strip()]

    def _split_segments(self, command: str) -> list[str]:
        normalized = command.replace("&&", ";").replace("||", ";")
        return [segment.strip() for segment in normalized.split(";") if segment.strip()]

    def _tokenize(self, segment: str) -> list[str]:
        try:
            return shlex.split(segment, posix=sys.platform != "win32")
        except ValueError:
            return segment.split()

    def _resolve_rule_action(self, rules: dict[str, str], pattern: str) -> str:
        action = "allow"
        for rule_pattern, rule_action in rules.items():
            if fnmatch.fnmatch(pattern, rule_pattern):
                action = rule_action
        return action
```

- [ ] **Step 4: Run the full bash tool test file to verify the policy tests pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_bash_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit the preflight policy logic**

```bash
git add app/tools/bash_tool.py tests/test_bash_tool.py
git commit -m "feat(tools): add bash tool policy preflight"
```

### Task 5: Implement timeout, interrupted execution metadata, and output truncation coverage

**Files:**
- Modify: `app/tools/bash_tool.py`
- Modify: `tests/test_bash_tool.py`
- Test: `tests/test_bash_tool.py`

- [ ] **Step 1: Write the failing timeout and truncation tests**

Add these tests to `tests/test_bash_tool.py`:

```python
def test_bash_tool_returns_timeout_metadata_when_command_expires(tmp_path: Path) -> None:
    tool = BashTool()
    runtime = _runtime(tmp_path)

    result = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments={
            "command": "python -c \"import time; time.sleep(1)\"",
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
            "command": "python -c \"print('a' * 20000)\"",
            "description": "Prints large output",
        },
    )

    assert result["metadata"]["truncated"] is True
    assert "...output truncated..." in result["output"]
```

- [ ] **Step 2: Run the timeout and truncation tests to verify they fail**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_bash_tool.py::test_bash_tool_returns_timeout_metadata_when_command_expires tests/test_bash_tool.py::test_bash_tool_truncates_large_output -v`
Expected: FAIL because timeout currently raises `subprocess.TimeoutExpired` instead of returning structured metadata.

- [ ] **Step 3: Return structured interruption metadata for timeout and preserve truncation behavior**

Update the subprocess execution block in `app/tools/bash_tool.py` to:

```python
        timeout_ms = request.timeout or self.DEFAULT_TIMEOUT_MS
        try:
            completed = subprocess.run(
                request.command,
                cwd=str(cwd),
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000,
            )
        except subprocess.TimeoutExpired as exc:
            output, truncated = self._truncate_output(exc.stdout or "", exc.stderr or "")
            if output == "(no output)":
                output = f"Command timed out after {timeout_ms} ms"
            else:
                output = output + f"\n\nCommand timed out after {timeout_ms} ms"
            return {
                "title": request.description,
                "output": output,
                "metadata": {
                    "exit_code": None,
                    "timed_out": True,
                    "aborted": False,
                    "truncated": truncated,
                    "cwd": str(cwd),
                    "command": request.command,
                },
            }
```

Leave the successful return path in place for non-timeout execution.

- [ ] **Step 4: Run the full bash tool test file to verify all behavior passes**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_bash_tool.py -v`
Expected: PASS

- [ ] **Step 5: Commit timeout and truncation behavior**

```bash
git add app/tools/bash_tool.py tests/test_bash_tool.py
git commit -m "feat(tools): add bash tool timeout handling"
```

### Task 6: Run integration-focused regression tests

**Files:**
- Modify: `tests/test_runtime_policy_resolvers.py`
- Modify: `tests/test_tool_resolver.py`
- Test: `tests/test_runtime_policy_resolvers.py`
- Test: `tests/test_tool_resolver.py`
- Test: `tests/test_bash_tool.py`

- [ ] **Step 1: Verify framework worker disabling still applies to runtime tools**

Ensure the existing test still asserts:

```python
    assert tool_policy["system_toolset"] == "none"
    assert tool_policy["model_tools_enabled"] is False
    assert tool_policy["runtime_tools_enabled"] is False
```

No new code is required if the existing test still covers this path.

- [ ] **Step 2: Run the full targeted regression suite**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py tests/test_tool_resolver.py tests/test_bash_tool.py -v`
Expected: PASS

- [ ] **Step 3: Run the broader runtime regression suite**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_workspace_resolver.py tests/test_runtime_assembler.py tests/test_tool_call_handler.py tests/test_tool_resolver.py tests/test_runtime_policy_resolvers.py tests/test_code_tool.py tests/test_plan_tool.py tests/test_prompt_composer.py tests/test_agent_run_input_state_machine.py -v`
Expected: PASS

- [ ] **Step 4: Commit the verified bash tool implementation**

```bash
git add app/schemas/bash_tool.py app/tools/bash_tool.py app/runtime/policy/tool_policy_resolver.py app/runtime/tools/tool_resolver.py tests/test_bash_tool.py tests/test_tool_resolver.py tests/test_runtime_policy_resolvers.py
git commit -m "feat(runtime): add bash tool with policy checks"
```
