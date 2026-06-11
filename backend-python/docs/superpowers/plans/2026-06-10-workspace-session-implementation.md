# Workspace Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared `WorkspaceSession` runtime capability for workspace file access, expose `code_tool` to internal worker agents, and begin converging file-writing tools onto the same workspace access path.

**Architecture:** Keep the current runtime pipeline intact and add one thin runtime capability object, `WorkspaceSession`, under `app/runtime/workspace/`. Inject it into `RuntimeBundle`, pass runtime into generic tool execution, implement `code_tool` as a model-visible worker tool that uses `runtime.workspace_session`, and migrate `plan_tool` file persistence away from direct `Path.cwd()` writes.

**Tech Stack:** Python 3.13, pytest, Pydantic, existing runtime/tool registry architecture

---

### Task 1: Add `WorkspaceSession` and its unit tests

**Files:**
- Create: `app/runtime/workspace/workspace_session.py`
- Modify: `tests/test_workspace_resolver.py`
- Test: `tests/test_workspace_resolver.py`

- [ ] **Step 1: Write the failing workspace session tests**

```python
from pathlib import Path

import pytest

from app.runtime.workspace.workspace_session import WorkspaceSession


def test_workspace_session_reads_and_writes_files(tmp_path: Path) -> None:
    session = WorkspaceSession(str(tmp_path))

    session.write_text("notes/todo.txt", "hello workspace")

    assert session.read_text("notes/todo.txt") == "hello workspace"


def test_workspace_session_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    session = WorkspaceSession(str(tmp_path))

    with pytest.raises(ValueError, match="escapes workspace root"):
        session.resolve_path("../secrets.txt")


def test_workspace_session_respects_overwrite_flag(tmp_path: Path) -> None:
    session = WorkspaceSession(str(tmp_path))
    session.write_text("README.md", "v1")

    with pytest.raises(ValueError, match="already exists"):
        session.write_text("README.md", "v2", overwrite=False)


def test_workspace_session_lists_directory_entries(tmp_path: Path) -> None:
    session = WorkspaceSession(str(tmp_path))
    session.write_text("app/main.py", "print('hi')")
    session.write_text("app/utils.py", "print('utils')")

    assert session.list_dir("app") == ["main.py", "utils.py"]
```

- [ ] **Step 2: Run the workspace session tests to verify they fail**

Run: `pytest tests/test_workspace_resolver.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing `WorkspaceSession` attribute errors

- [ ] **Step 3: Write the minimal `WorkspaceSession` implementation**

```python
from __future__ import annotations

from pathlib import Path


class WorkspaceSession:
    def __init__(self, workspace_root: str) -> None:
        root = Path(workspace_root).expanduser().resolve()
        if not root.exists():
            raise ValueError(f"workspace path does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"workspace path is not a directory: {root}")
        self.workspace_root = root

    def resolve_path(self, relative_path: str) -> Path:
        raw = (relative_path or ".").strip()
        target = Path(raw)
        if target.is_absolute():
            raise ValueError("absolute paths are not allowed")
        resolved = (self.workspace_root / target).resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError(f"path escapes workspace root: {relative_path}") from exc
        return resolved

    def exists(self, relative_path: str) -> bool:
        return self.resolve_path(relative_path).exists()

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        path = self.resolve_path(relative_path)
        if not path.exists() or not path.is_file():
            raise ValueError(f"file not found: {relative_path}")
        return path.read_text(encoding=encoding)

    def write_text(
        self,
        relative_path: str,
        content: str,
        *,
        encoding: str = "utf-8",
        overwrite: bool = True,
        create_parent: bool = True,
    ) -> None:
        path = self.resolve_path(relative_path)
        if path.exists() and not overwrite:
            raise ValueError(f"path already exists: {relative_path}")
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)

    def mkdir(self, relative_path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        self.resolve_path(relative_path).mkdir(parents=parents, exist_ok=exist_ok)

    def list_dir(self, relative_path: str = ".") -> list[str]:
        path = self.resolve_path(relative_path)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"directory not found: {relative_path}")
        return sorted(item.name for item in path.iterdir())

    def delete(self, relative_path: str, *, recursive: bool = False) -> None:
        path = self.resolve_path(relative_path)
        if not path.exists():
            raise ValueError(f"path not found: {relative_path}")
        if path.is_dir():
            if any(path.iterdir()) and not recursive:
                raise ValueError(f"recursive delete required: {relative_path}")
            if recursive:
                import shutil

                shutil.rmtree(path)
                return
            path.rmdir()
            return
        path.unlink()
```

- [ ] **Step 4: Run the workspace session tests to verify they pass**

Run: `pytest tests/test_workspace_resolver.py -v`
Expected: PASS

- [ ] **Step 5: Commit the workspace session foundation**

```bash
git add tests/test_workspace_resolver.py app/runtime/workspace/workspace_session.py
git commit -m "feat(runtime): add workspace session file access"
```

### Task 2: Inject `workspace_session` into runtime and pass runtime to generic tools

**Files:**
- Modify: `app/runtime/runtime_assembler.py`
- Modify: `app/runtime/tools/tool_registry.py`
- Modify: `tests/test_runtime_assembler.py`
- Modify: `tests/test_tool_call_handler.py`
- Test: `tests/test_runtime_assembler.py`
- Test: `tests/test_tool_call_handler.py`

- [ ] **Step 1: Write the failing runtime injection and dispatch tests**

```python
from app.runtime.workspace.workspace_session import WorkspaceSession


def test_runtime_assembler_injects_workspace_session() -> None:
    assembler = _assembler()
    agent_id = uuid4()
    run_id = uuid4()

    runtime = assembler.assemble(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="worker",
            workspace_id=uuid4(),
            root_run_id=run_id,
        ),
        AgentModel(
            agent_id=agent_id,
            agent_name="Worker",
            agent_kind="worker",
        ),
    )

    assert isinstance(runtime.workspace_session, WorkspaceSession)
    assert str(runtime.workspace_session.workspace_root).endswith("backend-python")


def test_tool_registry_default_dispatch_passes_runtime() -> None:
    generic_tool = RecordingGenericTool()
    runtime_bundle = _build_runtime_bundle({"question_tool": generic_tool})

    runtime_bundle.tool_registry.dispatch(
        runtime_bundle,
        [
            {
                "type": "function",
                "function": {
                    "name": "question_tool",
                    "arguments": '{"question":"Need clarification"}',
                },
            }
        ],
    )

    assert generic_tool.calls[0]["runtime"] is runtime_bundle
```

- [ ] **Step 2: Run the runtime and dispatch tests to verify they fail**

Run: `pytest tests/test_runtime_assembler.py tests/test_tool_call_handler.py -v`
Expected: FAIL because `RuntimeBundle` has no `workspace_session` and default dispatch does not pass `runtime`

- [ ] **Step 3: Implement runtime injection and generic runtime-aware dispatch**

```python
from app.runtime.workspace.workspace_session import WorkspaceSession


@dataclass(slots=True)
class RuntimeBundle:
    agent_run: AgentRunModel
    agent: AgentModel
    workspace_root: str
    role: str
    prompt_policy: dict[str, Any]
    tool_policy: dict[str, Any]
    executor_policy: dict[str, Any]
    tool_registry: ToolRegistry = field(default_factory=ToolRegistry)
    workspace_session: WorkspaceSession | None = None
    instruction_view: Any | None = None
    tool_view: Any | None = None
    prompt_view: Any | None = None
    runtime_snapshot: dict[str, Any] = field(default_factory=dict)


runtime_bundle = RuntimeBundle(
    agent_run=agent_run,
    agent=agent,
    workspace_root=workspace_root,
    role=role,
    prompt_policy=prompt_policy,
    tool_policy=tool_policy,
    executor_policy=executor_policy,
    workspace_session=WorkspaceSession(workspace_root),
    runtime_snapshot=runtime_snapshot,
)
```

```python
def default_invoke(tool: object, runtime: Any, arguments: Any) -> object:
    return tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        arguments=arguments,
    )
```

- [ ] **Step 4: Run the runtime and dispatch tests to verify they pass**

Run: `pytest tests/test_runtime_assembler.py tests/test_tool_call_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit runtime injection and dispatch changes**

```bash
git add app/runtime/runtime_assembler.py app/runtime/tools/tool_registry.py tests/test_runtime_assembler.py tests/test_tool_call_handler.py
git commit -m "refactor(runtime): inject workspace session into tools"
```

### Task 3: Make `code_tool` model-visible for internal workers and back it with `WorkspaceSession`

**Files:**
- Create: `app/schemas/code_tool.py`
- Modify: `app/tools/code_tool.py`
- Modify: `app/runtime/tools/tool_resolver.py`
- Modify: `tests/test_runtime_assembler.py`
- Modify: `tests/test_tool_resolver.py`
- Modify: `tests/test_prompt_composer.py`
- Modify: `tests/test_agent_run_input_state_machine.py`
- Test: `tests/test_tool_resolver.py`
- Test: `tests/test_runtime_assembler.py`
- Test: `tests/test_prompt_composer.py`
- Test: `tests/test_agent_run_input_state_machine.py`

- [ ] **Step 1: Write the failing worker tool visibility and code tool behavior tests**

```python
def test_worker_runtime_exposes_code_tool_definition() -> None:
    assembler = _assembler()
    agent_id = uuid4()
    run_id = uuid4()

    runtime = assembler.assemble(
        AgentRunModel(
            run_id=run_id,
            agent_id=agent_id,
            agent_kind="worker",
            workspace_id=uuid4(),
            root_run_id=run_id,
        ),
        AgentModel(
            agent_id=agent_id,
            agent_name="Worker",
            agent_kind="worker",
        ),
    )

    assert [item["function"]["name"] for item in runtime.tool_view.model_tools] == ["code_tool"]
    assert runtime.tool_view.tool_choice == "auto"


def test_code_tool_writes_workspace_file(tmp_path: Path) -> None:
    runtime = _build_runtime_bundle({})
    runtime.workspace_root = str(tmp_path)
    runtime.workspace_session = WorkspaceSession(str(tmp_path))

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
```

- [ ] **Step 2: Run the worker tool tests to verify they fail**

Run: `pytest tests/test_tool_resolver.py tests/test_runtime_assembler.py tests/test_prompt_composer.py tests/test_agent_run_input_state_machine.py -v`
Expected: FAIL because worker tools are not model-visible and `CodeTool` has no behavior

- [ ] **Step 3: Add the `code_tool` schema and minimal file actions**

```python
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class CodeToolRequest(BaseModel):
    action: Literal["read_file", "write_file", "list_files", "make_dir", "delete_path"]
    path: str = "."
    content: str = ""
    overwrite: bool = True
    recursive: bool = False


def build_code_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "code_tool",
            "description": "Read and write files inside the current workspace.",
            "parameters": CodeToolRequest.model_json_schema(),
        },
    }
```

```python
from __future__ import annotations

from app.schemas.code_tool import CodeToolRequest


class CodeTool:
    def run(self, *, runtime, arguments: CodeToolRequest, **_kwargs):
        workspace = runtime.workspace_session
        if workspace is None:
            raise ValueError("workspace_session is required")

        if arguments.action == "read_file":
            return {"status": "ok", "content": workspace.read_text(arguments.path)}
        if arguments.action == "write_file":
            workspace.write_text(arguments.path, arguments.content, overwrite=arguments.overwrite)
            return {"status": "ok", "path": arguments.path}
        if arguments.action == "list_files":
            return {"status": "ok", "entries": workspace.list_dir(arguments.path)}
        if arguments.action == "make_dir":
            workspace.mkdir(arguments.path)
            return {"status": "ok", "path": arguments.path}
        if arguments.action == "delete_path":
            workspace.delete(arguments.path, recursive=arguments.recursive)
            return {"status": "ok", "path": arguments.path}
        raise ValueError(f"unsupported action: {arguments.action}")
```

```python
registry.register(
    ToolSpec(
        name="code_tool",
        tool=CodeTool(),
        definition=build_code_tool_definition(),
        request_model=CodeToolRequest,
        invoke=default_invoke,
    )
)
```

Also update worker tool visibility expectations so internal worker runtimes expose `code_tool` in `model_tools`, and update prompt expectations so `model_visible_tools=code_tool` appears for worker prompts.

- [ ] **Step 4: Run the worker tool tests to verify they pass**

Run: `pytest tests/test_tool_resolver.py tests/test_runtime_assembler.py tests/test_prompt_composer.py tests/test_agent_run_input_state_machine.py -v`
Expected: PASS

- [ ] **Step 5: Commit the worker-facing `code_tool` implementation**

```bash
git add app/schemas/code_tool.py app/tools/code_tool.py app/runtime/tools/tool_resolver.py tests/test_tool_resolver.py tests/test_runtime_assembler.py tests/test_prompt_composer.py tests/test_agent_run_input_state_machine.py
git commit -m "feat(tools): add workspace-backed code tool"
```

### Task 4: Migrate `plan_tool` file persistence to `WorkspaceSession`

**Files:**
- Modify: `app/tools/plan_tool.py`
- Modify: `app/runtime/tools/tool_resolver.py`
- Modify: `tests/test_tool_call_handler.py`
- Create: `tests/test_plan_tool.py`
- Test: `tests/test_plan_tool.py`
- Test: `tests/test_tool_call_handler.py`

- [ ] **Step 1: Write the failing plan tool workspace persistence tests**

```python
from pathlib import Path
from uuid import uuid4

from app.repositories.plan_repository import PlanRepository
from app.runtime.workspace.workspace_session import WorkspaceSession
from app.schemas.plan_tool import PlanSnapshot, PlanStepPayload, PlanToolRequest
from app.tools.plan_tool import PlanTool


def test_plan_tool_writes_plan_inside_workspace(tmp_path: Path) -> None:
    tool = PlanTool(PlanRepository())
    runtime = type("Runtime", (), {})()
    runtime.workspace_session = WorkspaceSession(str(tmp_path))
    runtime.agent_run = type("Run", (), {"run_id": uuid4(), "workspace_id": uuid4()})()

    response = tool.run(
        run_id=runtime.agent_run.run_id,
        workspace_id=runtime.agent_run.workspace_id,
        runtime=runtime,
        request=PlanToolRequest(
            plan=PlanSnapshot(
                title="Execution Plan",
                goal="Ship workspace session",
                summary="Create shared workspace access",
                steps=[PlanStepPayload(step_id="1", content="write code")],
            )
        ),
    )

    output_path = tmp_path / ".AgentHub" / "plans" / f"{runtime.agent_run.run_id}.execution-plan.md"
    assert output_path.exists()
    assert response.file_path == str(output_path)
```

- [ ] **Step 2: Run the plan tool tests to verify they fail**

Run: `pytest tests/test_plan_tool.py tests/test_tool_call_handler.py -v`
Expected: FAIL because `PlanTool` still uses `Path.cwd()` and does not accept `runtime`

- [ ] **Step 3: Move plan file persistence behind `runtime.workspace_session`**

```python
class PlanTool:
    def run(self, *, run_id: UUID, workspace_id: UUID, request: PlanToolRequest, runtime=None) -> PlanToolResponse:
        workspace = getattr(runtime, "workspace_session", None)
        plan_relative_path = self._build_plan_relative_path(run_id)
        file_path = self._resolve_plan_file_path(plan_relative_path, workspace)

        snapshot = request.plan
        plan = self.plan_repository.get_by_run_id(run_id)
        if plan is None:
            plan = PlanModel(
                plan_id=uuid4(),
                run_id=run_id,
                workspace_id=workspace_id,
                file_path=file_path,
            )
            self.plan_repository.create(plan)

        ...

        plan.file_path = file_path
        plan.raw_document = self._render_markdown(run_id=run_id, snapshot=snapshot, updated_at=plan.updated_at)

        self.plan_repository.update(plan)
        self._write_plan_file(plan_relative_path, plan.raw_document, workspace=workspace)
```

```python
def _build_plan_relative_path(self, run_id: UUID) -> str:
    return f".AgentHub/plans/{run_id}.execution-plan.md"


def _resolve_plan_file_path(self, relative_path: str, workspace) -> str:
    if workspace is not None:
        return str(workspace.resolve_path(relative_path))
    return str(Path.cwd() / relative_path)


def _write_plan_file(self, relative_path: str, content: str, *, workspace=None) -> None:
    if workspace is not None:
        workspace.write_text(relative_path, content)
        return
    path = Path.cwd() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
```

Update `_invoke_plan_tool()` to pass `runtime=runtime` so `PlanTool` can consume the workspace capability.

- [ ] **Step 4: Run the plan tool tests to verify they pass**

Run: `pytest tests/test_plan_tool.py tests/test_tool_call_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit the plan tool workspace migration**

```bash
git add app/tools/plan_tool.py app/runtime/tools/tool_resolver.py tests/test_plan_tool.py tests/test_tool_call_handler.py
git commit -m "refactor(plan): persist plan files through workspace session"
```

### Task 5: Run the focused verification suite and final review

**Files:**
- Modify: `docs/superpowers/plans/2026-06-10-workspace-session-implementation.md`
- Test: `tests/test_workspace_resolver.py`
- Test: `tests/test_runtime_assembler.py`
- Test: `tests/test_tool_call_handler.py`
- Test: `tests/test_tool_resolver.py`
- Test: `tests/test_prompt_composer.py`
- Test: `tests/test_agent_run_input_state_machine.py`
- Test: `tests/test_plan_tool.py`

- [ ] **Step 1: Run the complete focused verification suite**

Run: `pytest tests/test_workspace_resolver.py tests/test_runtime_assembler.py tests/test_tool_call_handler.py tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_agent_run_input_state_machine.py tests/test_plan_tool.py -v`
Expected: PASS

- [ ] **Step 2: Run a broader smoke suite if the focused suite passes**

Run: `pytest tests/test_runtime_policy_resolvers.py tests/test_instruction_resolver.py tests/test_framework_worker_flow.py -v`
Expected: PASS

- [ ] **Step 3: Update the plan checklist in place**

```markdown
- [x] Task 1 complete
- [x] Task 2 complete
- [x] Task 3 complete
- [x] Task 4 complete
- [x] Task 5 verification complete
```

- [ ] **Step 4: Commit final verification updates if the plan file changed**

```bash
git add docs/superpowers/plans/2026-06-10-workspace-session-implementation.md
git commit -m "docs: update workspace session implementation plan status"
```
