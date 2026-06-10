# External Code Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace framework executor mode switching with explicit `claude_code_tool`, `codex_tool`, and `opencode_tool` runtime tools while moving agent configuration to explicit `tool_config` and `executor_config` models.

**Architecture:** All agents continue to run on the internal LLM executor. Agent-visible capabilities are derived only from explicit `tool_config.tools`, and the three external coding tools share a common subprocess runner that reuses the existing framework adapter command-building and response-parsing logic.

**Tech Stack:** Python, Pydantic, pytest, internal LLM runtime, subprocess-based CLI adapters, PowerShell 5.1 test commands on Windows

---

## File Structure

**Create**
- `app/models/agent_tool_config.py` - typed tool config models for agent configuration
- `app/models/agent_executor_config.py` - typed internal executor config model
- `app/schemas/claude_code_tool.py` - request schema and tool definition for `claude_code_tool`
- `app/schemas/codex_tool.py` - request schema and tool definition for `codex_tool`
- `app/schemas/opencode_tool.py` - request schema and tool definition for `opencode_tool`
- `app/tools/external_code_runner.py` - shared subprocess backend for external code tools
- `app/tools/claude_code_tool.py` - runtime wrapper for Claude Code CLI
- `app/tools/codex_tool.py` - runtime wrapper for Codex CLI
- `app/tools/opencode_tool.py` - runtime wrapper for OpenCode CLI

**Modify**
- `app/models/agent.py` - replace `tool_policy` and `executor_policy` with typed config fields
- `app/runtime/snapshot/runtime_snapshot_resolver.py` - emit `tool_config` and `executor_config`
- `app/runtime/runtime_assembler.py` - carry resolved tool and executor config in `RuntimeBundle`
- `app/runtime/policy/tool_policy_resolver.py` - convert into explicit tool config normalization
- `app/runtime/policy/executor_policy_resolver.py` - convert into internal-only executor config normalization
- `app/runtime/tools/tool_resolver.py` - register tools from explicit tool names instead of `system_toolset`
- `app/runtime/prompt/prompt_composer.py` - remove `system_toolset` and framework-executor prompt branches
- `app/runtime/prompt/mode/orchestrator_mode_prompt.py` - gate tool guidance on actual configured tools
- `app/runtime/prompt/mode/worker_mode_prompt.py` - gate tool guidance on actual configured tools and mention external code tools
- `app/llm/llm_executor.py` - make `AgentExecutorFactory` always resolve internal executor and remove framework executor runtime path
- `app/llm/framework_adapters/claude_code_adapter.py` - take explicit tool options instead of `runtime.executor_policy`
- `app/llm/framework_adapters/codex_cli_adapter.py` - take explicit tool options instead of `runtime.executor_policy`
- `app/llm/framework_adapters/opencode_adapter.py` - take explicit tool options instead of `runtime.executor_policy`
- `app/database/seed.py` - seed explicit tool lists for orchestrator and worker agents

**Test**
- `tests/test_runtime_policy_resolvers.py`
- `tests/test_runtime_assembler.py`
- `tests/test_tool_resolver.py`
- `tests/test_prompt_composer.py`
- `tests/test_llm_executor.py`
- `tests/test_delegate_chain_internal_code_tool.py`
- `tests/test_delegate_chain_internal_bash_tool.py`
- `tests/test_delegate_chain_e2e_internal_llm.py`
- `tests/test_agent_run_input_state_machine.py`
- `tests/test_instruction_resolver.py`
- `tests/test_code_tool.py`
- `tests/test_bash_tool.py`
- `tests/test_plan_tool.py`
- `tests/test_tool_call_handler.py`
- `tests/test_claude_code_tool.py`
- `tests/test_opencode_tool.py`
- `tests/test_external_code_runner.py`

### Task 1: Replace Agent Config Models

**Files:**
- Create: `app/models/agent_tool_config.py`
- Create: `app/models/agent_executor_config.py`
- Modify: `app/models/agent.py`
- Modify: `app/runtime/snapshot/runtime_snapshot_resolver.py`
- Modify: `app/runtime/runtime_assembler.py`
- Test: `tests/test_runtime_policy_resolvers.py`
- Test: `tests/test_runtime_assembler.py`

- [ ] **Step 1: Write the failing config model tests**

```python
from uuid import uuid4

from app.models.agent import AgentModel


def test_agent_model_uses_explicit_tool_and_executor_config() -> None:
    agent = AgentModel(
        agent_id=uuid4(),
        agent_name="Worker",
        agent_kind="worker",
        tool_config={
            "tools": [
                {"name": "code_tool"},
                {"name": "bash_tool", "options": {"command_policies": {"bash": {"*": "allow"}}}},
            ],
            "auto_tool_choice": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )

    assert [tool.name for tool in agent.tool_config.tools] == ["code_tool", "bash_tool"]
    assert agent.executor_config.kind == "internal_llm"
    assert agent.executor_config.model == "gpt-test"


def test_runtime_snapshot_resolver_emits_new_config_fields() -> None:
    agent = AgentModel(
        agent_id=uuid4(),
        agent_name="Orchestrator",
        agent_kind="orchestrator",
        tool_config={"tools": [{"name": "plan_tool"}, {"name": "delegate_tool"}, {"name": "bash_tool"}]},
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )

    snapshot = RuntimeSnapshotResolver().build_default_snapshot(agent)

    assert snapshot["tool_config"]["tools"][0]["name"] == "plan_tool"
    assert snapshot["executor_config"]["kind"] == "internal_llm"
    assert "tool_policy" not in snapshot
    assert "executor_policy" not in snapshot
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py tests/test_runtime_assembler.py -v
```

Expected: FAIL because `AgentModel` does not yet accept `tool_config` and `executor_config`, and runtime snapshot assertions still reference `tool_policy` / `executor_policy`.

- [ ] **Step 3: Write the minimal config model implementation**

```python
# app/models/agent_tool_config.py
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentToolConfig(BaseModel):
    name: Literal[
        "plan_tool",
        "delegate_tool",
        "code_tool",
        "bash_tool",
        "claude_code_tool",
        "codex_tool",
        "opencode_tool",
        "question_tool",
    ]
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class AgentToolsetConfig(BaseModel):
    tools: list[AgentToolConfig] = Field(default_factory=list)
    auto_tool_choice: bool = False
    model_tools_enabled: bool = True
    runtime_tools_enabled: bool = True
```

```python
# app/models/agent_executor_config.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class AgentExecutorConfig(BaseModel):
    kind: Literal["internal_llm"] = "internal_llm"
    provider: str = "openai_compatible"
    model: str = ""
```

```python
# app/models/agent.py
from app.models.agent_executor_config import AgentExecutorConfig
from app.models.agent_tool_config import AgentToolsetConfig


class AgentModel(BaseModel):
    ...
    prompt_policy: dict[str, Any] = Field(default_factory=dict)
    tool_config: AgentToolsetConfig = Field(default_factory=AgentToolsetConfig)
    executor_config: AgentExecutorConfig = Field(default_factory=AgentExecutorConfig)
    ...
```

```python
# app/runtime/snapshot/runtime_snapshot_resolver.py
snapshot.setdefault("tool_config", agent.tool_config.model_dump())
snapshot.setdefault("executor_config", agent.executor_config.model_dump())
```

```python
# app/runtime/runtime_assembler.py
@dataclass(slots=True)
class RuntimeBundle:
    ...
    tool_config: dict[str, Any]
    executor_config: dict[str, Any]
    ...

    def uses_internal_executor(self) -> bool:
        return self.executor_config.get("kind", "internal_llm") == "internal_llm"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py tests/test_runtime_assembler.py -v
```

Expected: PASS with the updated runtime fields and no references to `tool_policy` / `executor_policy` in these tests.

- [ ] **Step 5: Commit**

```bash
git add app/models/agent_tool_config.py app/models/agent_executor_config.py app/models/agent.py app/runtime/snapshot/runtime_snapshot_resolver.py app/runtime/runtime_assembler.py tests/test_runtime_policy_resolvers.py tests/test_runtime_assembler.py
git commit -m "feat(runtime): add explicit agent tool and executor config"
```

### Task 2: Resolve and Register Explicit Tools

**Files:**
- Modify: `app/runtime/policy/tool_policy_resolver.py`
- Modify: `app/runtime/policy/executor_policy_resolver.py`
- Modify: `app/runtime/tools/tool_resolver.py`
- Modify: `app/runtime/prompt/prompt_composer.py`
- Modify: `tests/test_tool_resolver.py`
- Modify: `tests/test_prompt_composer.py`
- Modify: `tests/test_instruction_resolver.py`
- Test: `tests/test_runtime_policy_resolvers.py`

- [ ] **Step 1: Write the failing resolver and prompt tests**

```python
from uuid import uuid4

from app.models.agent import AgentModel
from app.models.agent_run import AgentRunModel
from app.runtime.runtime_assembler import RuntimeBundle
from app.runtime.tools.tool_resolver import ToolResolver


def test_tool_resolver_registers_only_explicit_enabled_tools(plan_repository) -> None:
    runtime = RuntimeBundle(
        agent_run=AgentRunModel(run_id=uuid4(), agent_id=uuid4(), agent_kind="worker", workspace_id=uuid4()),
        agent=AgentModel(
            agent_id=uuid4(),
            agent_name="Worker",
            agent_kind="worker",
            tool_config={
                "tools": [
                    {"name": "code_tool"},
                    {"name": "bash_tool"},
                    {"name": "claude_code_tool", "enabled": False},
                ],
                "auto_tool_choice": True,
            },
        ),
        workspace_root="E:/workspace",
        role="worker",
        prompt_policy={},
        tool_config={
            "tools": [
                {"name": "code_tool", "enabled": True, "options": {}},
                {"name": "bash_tool", "enabled": True, "options": {}},
                {"name": "claude_code_tool", "enabled": False, "options": {}},
            ],
            "auto_tool_choice": True,
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
        },
        executor_config={"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"},
    )

    tool_view = ToolResolver(plan_repository).resolve(runtime)

    assert [item.name for item in tool_view.system_tools] == ["code_tool", "bash_tool"]
    assert [item["function"]["name"] for item in tool_view.model_tools] == ["code_tool", "bash_tool"]
    assert tool_view.tool_choice == "auto"


def test_prompt_composer_lists_explicit_visible_tools_without_system_toolset() -> None:
    ...
    assert "system_toolset=" not in prompt_view.system_prompt
    assert "model_visible_tools=plan_tool,delegate_tool,bash_tool" in prompt_view.system_prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_instruction_resolver.py tests/test_runtime_policy_resolvers.py -v
```

Expected: FAIL because resolver code still depends on `system_toolset` and prompt rendering still emits `system_toolset=` or framework-executor branches.

- [ ] **Step 3: Write the minimal explicit tool resolution implementation**

```python
# app/runtime/policy/executor_policy_resolver.py
class ExecutorPolicyResolver:
    def resolve(self, runtime_snapshot: dict[str, Any]) -> dict[str, Any]:
        executor_config = {
            "kind": "internal_llm",
            "provider": "openai_compatible",
            "model": "",
        }
        executor_config.update(runtime_snapshot.get("executor_config", {}))
        return executor_config
```

```python
# app/runtime/policy/tool_policy_resolver.py
class ToolPolicyResolver:
    def resolve(self, runtime_snapshot: dict[str, Any], **_kwargs) -> dict[str, Any]:
        tool_config = {
            "tools": [],
            "auto_tool_choice": False,
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
        }
        tool_config.update(runtime_snapshot.get("tool_config", {}))
        return tool_config
```

```python
# app/runtime/tools/tool_resolver.py
def resolve(self, runtime: RuntimeBundle) -> ToolView:
    registry = ToolRegistry()
    for item in runtime.tool_config.get("tools", []):
        if not item.get("enabled", True):
            continue
        self._register_named_tool(registry, item["name"])
    runtime.tool_registry = registry
    model_tools_enabled = bool(runtime.tool_config.get("model_tools_enabled", True))
    runtime_tools_enabled = bool(runtime.tool_config.get("runtime_tools_enabled", True))
    model_tools = registry.get_tool_definitions() if model_tools_enabled else []
    tool_choice = "auto" if model_tools and runtime.tool_config.get("auto_tool_choice", False) else None
    ...
```

```python
# app/runtime/prompt/prompt_composer.py
def _build_provider_section(self, runtime: RuntimeBundle) -> str:
    provider = runtime.executor_config.get("provider") or "default"
    return (
        "[PROVIDER]\n"
        "executor_kind=internal_llm\n"
        f"provider={provider}\n"
        f"prompt_profile={runtime.prompt_policy.get('system_profile', '')}"
    )


def _build_tool_section(self, runtime: RuntimeBundle) -> str:
    model_tools = [item["function"]["name"] for item in runtime.tool_view.model_tools]
    visible = ",".join(model_tools) if model_tools else "(none)"
    runtime_tools = ",".join(item.name for item in runtime.tool_view.system_tools) or "(none)"
    return "[TOOLS]\ntool_runtime=internal\n" f"runtime_toolset={runtime_tools}\nmodel_visible_tools={visible}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_instruction_resolver.py tests/test_runtime_policy_resolvers.py -v
```

Expected: PASS with explicit tool lists driving prompt visibility and registry construction.

- [ ] **Step 5: Commit**

```bash
git add app/runtime/policy/tool_policy_resolver.py app/runtime/policy/executor_policy_resolver.py app/runtime/tools/tool_resolver.py app/runtime/prompt/prompt_composer.py tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_instruction_resolver.py tests/test_runtime_policy_resolvers.py
git commit -m "feat(runtime): resolve tools from explicit tool config"
```

### Task 3: Add Shared External Code Runner and Tool Schemas

**Files:**
- Create: `app/tools/external_code_runner.py`
- Create: `app/schemas/claude_code_tool.py`
- Create: `app/schemas/codex_tool.py`
- Create: `app/schemas/opencode_tool.py`
- Create: `app/tools/claude_code_tool.py`
- Create: `app/tools/codex_tool.py`
- Create: `app/tools/opencode_tool.py`
- Modify: `app/llm/framework_adapters/claude_code_adapter.py`
- Modify: `app/llm/framework_adapters/codex_cli_adapter.py`
- Modify: `app/llm/framework_adapters/opencode_adapter.py`
- Modify: `app/runtime/tools/tool_resolver.py`
- Test: `tests/test_external_code_runner.py`
- Test: `tests/test_claude_code_tool.py`
- Test: `tests/test_opencode_tool.py`

- [ ] **Step 1: Write the failing runner and tool tests**

```python
from app.llm.llm_types import LlmResponse


def test_external_code_runner_executes_claude_adapter(monkeypatch, runtime_bundle) -> None:
    captured = {}

    def fake_run(*args, **kwargs):
        captured["cwd"] = kwargs["cwd"]
        captured["timeout"] = kwargs["timeout"]
        return SimpleNamespace(stdout='{"content":"done"}', stderr="", returncode=0)

    monkeypatch.setattr("app.tools.external_code_runner.subprocess.run", fake_run)

    response = ExternalCodeRunner().run(
        runtime=runtime_bundle,
        framework="claude",
        tool_options={"command": "claude", "timeout_seconds": 90, "allowed_tools": ["Read", "Edit"]},
        prompt="Update the file",
    )

    assert response.content == "done"
    assert captured["cwd"] == runtime_bundle.workspace_root
    assert captured["timeout"] == 90


def test_claude_code_tool_uses_agent_tool_options(runtime_bundle, monkeypatch) -> None:
    runtime_bundle.tool_config = {
        "tools": [
            {"name": "claude_code_tool", "enabled": True, "options": {"command": "claude", "timeout_seconds": 90}}
        ],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": False,
    }

    monkeypatch.setattr(
        "app.tools.claude_code_tool.ExternalCodeRunner.run",
        lambda self, **kwargs: LlmResponse(content="tool ok", raw=kwargs),
    )

    result = ClaudeCodeTool().run(runtime=runtime_bundle, arguments={"prompt": "Refactor app.py"})

    assert result["status"] == "ok"
    assert result["content"] == "tool ok"
    assert result["framework"] == "claude"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_external_code_runner.py tests/test_claude_code_tool.py tests/test_codex_tool.py tests/test_opencode_tool.py -v
```

Expected: FAIL because the runner and new tool modules do not exist yet.

- [ ] **Step 3: Write the minimal shared runner and tool implementation**

```python
# app/tools/external_code_runner.py
from __future__ import annotations

import os
import subprocess

from app.llm.framework_adapters import resolve_framework_adapter
from app.llm.llm_types import LlmMessage, LlmRequest, LlmResponse


class ExternalCodeRunner:
    def run(self, *, runtime, framework: str, tool_options: dict[str, object], prompt: str) -> LlmResponse:
        adapter = resolve_framework_adapter(framework)
        request = LlmRequest(
            system_prompt="",
            context_prompt="",
            messages=[LlmMessage(role="user", content=prompt)],
            tools=[],
            tool_choice=None,
            model=runtime.executor_config.get("model", ""),
        )
        command_args, env = adapter.build_command(runtime=runtime, request=request, env=dict(os.environ), options=tool_options)
        completed = subprocess.run(
            command_args,
            cwd=runtime.workspace_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(tool_options.get("timeout_seconds", 300)),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "external code tool failed").strip())
        return adapter.parse_response(completed)
```

```python
# app/schemas/claude_code_tool.py
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ClaudeCodeToolRequest(BaseModel):
    prompt: str


def build_claude_code_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "claude_code_tool",
            "description": "Delegate coding work to Claude Code inside the current workspace.",
            "parameters": ClaudeCodeToolRequest.model_json_schema(),
        },
    }
```

```python
# app/tools/claude_code_tool.py
from __future__ import annotations

from app.schemas.claude_code_tool import ClaudeCodeToolRequest
from app.tools.external_code_runner import ExternalCodeRunner


class ClaudeCodeTool:
    def __init__(self, runner: ExternalCodeRunner | None = None) -> None:
        self.runner = runner or ExternalCodeRunner()

    def run(self, *, runtime, arguments: ClaudeCodeToolRequest | dict, **_kwargs):
        request = arguments if isinstance(arguments, ClaudeCodeToolRequest) else ClaudeCodeToolRequest.model_validate(arguments)
        tool_options = next(
            (item.get("options", {}) for item in runtime.tool_config.get("tools", []) if item.get("name") == "claude_code_tool"),
            {},
        )
        response = self.runner.run(runtime=runtime, framework="claude", tool_options=tool_options, prompt=request.prompt)
        return {"status": "ok", "framework": "claude", "content": response.content, "raw": response.raw}
```

Implement `CodexTool` and `OpenCodeTool` with the same structure, changing only the request type, definition builder, and `framework=` value. In this phase, only `claude_code_tool` and `opencode_tool` need verification coverage because Codex is not connected in the current environment.

Update the adapters to accept `options`:

```python
def build_command(self, runtime, request, env, options: dict[str, object]) -> tuple[list[str], dict[str, str]]:
    command = str(options.get("command") or self.framework_name)
```

Register all three tools by name in `ToolResolver._register_named_tool(...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_external_code_runner.py tests/test_claude_code_tool.py tests/test_opencode_tool.py -v
```

Expected: PASS with `claude_code_tool` and `opencode_tool` using the shared subprocess runner and provider-specific adapters.

- [ ] **Step 5: Commit**

```bash
git add app/tools/external_code_runner.py app/schemas/claude_code_tool.py app/schemas/codex_tool.py app/schemas/opencode_tool.py app/tools/claude_code_tool.py app/tools/codex_tool.py app/tools/opencode_tool.py app/llm/framework_adapters/claude_code_adapter.py app/llm/framework_adapters/codex_cli_adapter.py app/llm/framework_adapters/opencode_adapter.py app/runtime/tools/tool_resolver.py tests/test_external_code_runner.py tests/test_claude_code_tool.py tests/test_opencode_tool.py
git commit -m "feat(tools): add external code tool runner"
```

### Task 4: Remove Framework Executor Runtime Path

**Files:**
- Modify: `app/llm/llm_executor.py`
- Modify: `tests/test_llm_executor.py`
- Modify: `tests/test_runtime_assembler.py`
- Modify: `tests/test_runtime_policy_resolvers.py`

- [ ] **Step 1: Write the failing executor tests**

```python
from app.llm.llm_executor import AgentExecutorFactory, InternalLlmExecutor


def test_executor_factory_always_selects_internal_executor(runtime_bundle) -> None:
    runtime_bundle.executor_config = {"kind": "internal_llm", "provider": "openai_compatible", "model": "gpt-test"}

    executor = AgentExecutorFactory().resolve(runtime_bundle)

    assert isinstance(executor, InternalLlmExecutor)


def test_claude_adapter_uses_explicit_tool_options(monkeypatch, runtime_bundle) -> None:
    adapter = ClaudeCodeAdapter()
    command_args, _env = adapter.build_command(
        runtime=runtime_bundle,
        request=LlmRequest(system_prompt="system", context_prompt="context", messages=[LlmMessage(role="user", content="hello")]),
        env={},
        options={"command": "claude", "allowed_tools": ["Read", "Edit"]},
    )

    assert "--allowedTools" in command_args or "--allowedtools" in " ".join(command_args).lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_llm_executor.py tests/test_runtime_assembler.py tests/test_runtime_policy_resolvers.py -v
```

Expected: FAIL because executor tests still expect `FrameworkCliExecutor` and adapter signatures still depend on executor policy fields.

- [ ] **Step 3: Write the minimal internal-only executor implementation**

```python
# app/llm/llm_executor.py
class AgentExecutorFactory:
    def resolve(self, runtime: RuntimeBundle) -> AgentExecutor:
        return InternalLlmExecutor()
```

Remove `FrameworkCliExecutor` from the active runtime path. If the class remains temporarily in the file during refactor, remove its tests and any call sites in this task.

Update the adapter-focused tests in `tests/test_llm_executor.py` to exercise command construction through explicit `options` and the shared external code runner rather than through `FrameworkCliExecutor.execute(...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_llm_executor.py tests/test_runtime_assembler.py tests/test_runtime_policy_resolvers.py -v
```

Expected: PASS with internal-only executor selection and adapter tests moved to the tool backend model.

- [ ] **Step 5: Commit**

```bash
git add app/llm/llm_executor.py tests/test_llm_executor.py tests/test_runtime_assembler.py tests/test_runtime_policy_resolvers.py
git commit -m "refactor(runtime): remove framework executor mode"
```

### Task 5: Prompt, Seed, Delegate Flow, and Regression Coverage

**Files:**
- Modify: `app/runtime/prompt/mode/orchestrator_mode_prompt.py`
- Modify: `app/runtime/prompt/mode/worker_mode_prompt.py`
- Modify: `app/database/seed.py`
- Modify: `tests/test_delegate_chain_internal_code_tool.py`
- Modify: `tests/test_delegate_chain_internal_bash_tool.py`
- Modify: `tests/test_delegate_chain_e2e_internal_llm.py`
- Modify: `tests/test_agent_run_input_state_machine.py`
- Modify: `tests/test_code_tool.py`
- Modify: `tests/test_bash_tool.py`
- Modify: `tests/test_plan_tool.py`
- Modify: `tests/test_tool_call_handler.py`

- [ ] **Step 1: Write the failing regression tests**

```python
def test_seeded_orchestrator_uses_explicit_tool_list() -> None:
    seed_memory_store()
    orchestrator = next(agent for agent in STORE.agents.values() if agent.agent_kind == "orchestrator")

    assert [tool.name for tool in orchestrator.tool_config.tools] == ["plan_tool", "delegate_tool", "bash_tool"]


def test_worker_prompt_mentions_external_code_tools_only_when_configured(runtime_bundle) -> None:
    runtime_bundle.tool_config = {
        "tools": [{"name": "code_tool", "enabled": True, "options": {}}, {"name": "bash_tool", "enabled": True, "options": {}}],
        "model_tools_enabled": True,
        "runtime_tools_enabled": True,
        "auto_tool_choice": True,
    }
    ...
    assert "claude_code_tool" not in prompt_view.system_prompt
```

Add one delegate-chain regression showing a worker can call `claude_code_tool` when explicitly configured:

```python
assert executor.calls[1]["tools"] == ["code_tool", "bash_tool", "claude_code_tool"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py tests/test_agent_run_input_state_machine.py tests/test_code_tool.py tests/test_bash_tool.py tests/test_plan_tool.py tests/test_tool_call_handler.py tests/test_prompt_composer.py -v
```

Expected: FAIL because fixtures, prompt assertions, and delegate-chain expectations still assume old config fields or old tool visibility shapes.

- [ ] **Step 3: Write the minimal regression and seed updates**

```python
# app/database/seed.py
STORE.agents[orchestrator_agent_id] = AgentModel(
    agent_id=orchestrator_agent_id,
    agent_name="Orchestrator",
    agent_kind="orchestrator",
    tool_config={"tools": [{"name": "plan_tool"}, {"name": "delegate_tool"}, {"name": "bash_tool"}], "auto_tool_choice": True},
)

STORE.agents[worker_agent_id] = AgentModel(
    agent_id=worker_agent_id,
    agent_name="Worker",
    agent_kind="worker",
    tool_config={"tools": [{"name": "code_tool"}, {"name": "bash_tool"}], "auto_tool_choice": True},
)
```

Update prompt builders to inspect actual configured tool names before emitting role guidance about `bash_tool`, `code_tool`, or external code tools.

Update delegate-chain tests and runtime fixtures so workers and orchestrators build their tool lists explicitly in `tool_config.tools`.

- [ ] **Step 4: Run the targeted regression suites**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py tests/test_agent_run_input_state_machine.py tests/test_code_tool.py tests/test_bash_tool.py tests/test_plan_tool.py tests/test_tool_call_handler.py tests/test_prompt_composer.py -v
```

Expected: PASS with explicit tool-config fixtures and stable internal LLM tool loops.

- [ ] **Step 5: Run the broad verification suite**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py tests/test_runtime_assembler.py tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_instruction_resolver.py tests/test_external_code_runner.py tests/test_claude_code_tool.py tests/test_codex_tool.py tests/test_opencode_tool.py tests/test_llm_executor.py tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py tests/test_agent_run_input_state_machine.py tests/test_code_tool.py tests/test_bash_tool.py tests/test_plan_tool.py tests/test_tool_call_handler.py -v
```

Expected: PASS with all new config paths and external code tools integrated.

- [ ] **Step 6: Commit**

```bash
git add app/runtime/prompt/mode/orchestrator_mode_prompt.py app/runtime/prompt/mode/worker_mode_prompt.py app/database/seed.py tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py tests/test_agent_run_input_state_machine.py tests/test_code_tool.py tests/test_bash_tool.py tests/test_plan_tool.py tests/test_tool_call_handler.py tests/test_prompt_composer.py
git commit -m "test(runtime): migrate flows to explicit external code tools"
```

## Self-Review

### Spec coverage

- Explicit `tool_config` and `executor_config`: covered by Task 1 and Task 2.
- No `system_toolset`: covered by Task 2 and Task 5.
- Shared backend for `claude_code_tool`, `codex_tool`, `opencode_tool`: covered by Task 3.
- Internal LLM only execution path: covered by Task 4.
- Prompt and regression updates: covered by Task 5.

No uncovered spec requirement remains.

### Placeholder scan

- No `TBD`, `TODO`, or deferred implementation markers remain.
- Every task contains exact files, exact commands, and concrete code examples.

### Type consistency

- `tool_config` is used consistently as the runtime-facing replacement for `tool_policy`.
- `executor_config` is used consistently as the runtime-facing replacement for `executor_policy`.
- External tool names are used consistently across models, resolver steps, and tests.
