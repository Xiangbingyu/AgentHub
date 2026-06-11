# MCP 与 Skills Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不迁移现有 `app/tools/` 与 `app/runtime/tools/` 主链路的前提下，增量接入 `app/mcp/service.py`、`app/skills/registry.py` 以及对应 runtime 子目录，并让 internal LLM agent 可以通过 `skill_tool` 和动态 MCP tools 使用这些能力。

**Architecture:** 保留现有 `ToolResolver` / `ToolRegistry` 作为统一 tool 汇合点。`app/mcp/service.py` 负责 MCP 资产与远端调用，`app/skills/registry.py` 负责 skill 资产与按名读取；`app/runtime/mcp/resolver.py` 与 `app/runtime/skills/resolver.py` 只负责把它们接入单次 run，并把结果挂到 `RuntimeBundle`。

**Tech Stack:** Python 3.11+, Pydantic models, existing runtime assembler/resolver pattern, pytest

---

## File Structure

### New Files

- `app/models/agent_skill_config.py`
  - 定义 `AgentSkillConfig`，承载 `builtins_enabled`、`paths`、`include_global`、`allowed_skills`
- `app/models/agent_mcp_config.py`
  - 定义 `AgentMcpConfig`，承载 `enabled` 与 `servers`
- `app/runtime/skills/resolver.py`
  - 从 snapshot / agent config 构建本次 run 的 `skill_registry`
- `app/runtime/mcp/resolver.py`
  - 从 snapshot / agent config 构建本次 run 的 `mcp_runtime`
- `app/skills/registry.py`
  - 加载 built-in skills、workspace skills，提供 `all()` / `available()` / `get(name)` / `render_available_skills()`
- `app/mcp/service.py`
  - 读取 server config，返回 MCP runtime 对象，并把远端 tool 定义适配成现有 `ToolSpec`
- `app/tools/skill_tool.py`
  - 根据 `runtime.skill_registry` 按名加载 skill 内容
- `app/schemas/skill_tool.py`
  - 定义 `SkillToolRequest` 和 `build_skill_tool_definition()`
- `tests/test_skill_registry.py`
  - 验证 built-in / workspace skill 加载、覆盖规则、摘要渲染
- `tests/test_skill_tool.py`
  - 验证 `skill_tool` 按名装载 skill
- `tests/test_mcp_service.py`
  - 验证 MCP runtime 构建、tool name 归一化、ToolSpec 生成
- `tests/test_runtime_skill_resolver.py`
  - 验证 runtime skills resolver 将 skill registry 注入 bundle
- `tests/test_runtime_mcp_resolver.py`
  - 验证 runtime mcp resolver 将 mcp runtime 注入 bundle

### Modified Files

- `app/models/agent.py`
  - 增加 `skill_config` 与 `mcp_config`
- `app/runtime/snapshot/runtime_snapshot_resolver.py`
  - snapshot 增加 `skill_config` 与 `mcp_config`
- `app/runtime/runtime_assembler.py`
  - `RuntimeBundle` 增加 `skill_config`、`mcp_config`、`skill_registry`、`mcp_runtime`
  - `RuntimeAssembler` 调用新 resolver
- `app/runtime/tools/tool_resolver.py`
  - 注册 `skill_tool`
  - 合并 `runtime.mcp_runtime` 导出的动态 tools
- `app/runtime/prompt/prompt_composer.py`
  - 在 system prompt 中注入 `available_skills`
- `tests/test_tool_resolver.py`
  - 增加 `skill_tool` 和 MCP tools 汇总断言
- `tests/test_instruction_resolver.py`
  - 更新 `RuntimeBundle` 初始化辅助函数，补齐新字段
- `tests/test_runtime_policy_resolvers.py`
  - 增加 `skill_config` 与 `mcp_config` 默认值断言

### Existing Files To Reuse As References

- `app/runtime/tools/tool_resolver.py`
- `app/runtime/runtime_assembler.py`
- `app/runtime/snapshot/runtime_snapshot_resolver.py`
- `app/tools/claude_code_tool.py`
- `app/tools/opencode_tool.py`
- `tests/test_tool_resolver.py`
- `tests/test_instruction_resolver.py`

### Built-in Asset Locations

- `app/skills/builtins/`
  - 存放 `.md` skill 文本资产
- `app/mcp/builtins/`
  - 本阶段不单独建目录；built-in preset 先放在 `app/mcp/service.py` 内部常量中

---

### Task 1: Add Agent Config And Runtime Snapshot Plumbing

**Files:**
- Create: `app/models/agent_skill_config.py`
- Create: `app/models/agent_mcp_config.py`
- Modify: `app/models/agent.py`
- Modify: `app/runtime/snapshot/runtime_snapshot_resolver.py`
- Test: `tests/test_runtime_policy_resolvers.py`

- [ ] **Step 1: Write the failing config snapshot tests**

Add these assertions to `tests/test_runtime_policy_resolvers.py`:

```python
def test_runtime_snapshot_includes_skill_and_mcp_config_defaults() -> None:
    agent = AgentModel(
        agent_id=uuid4(),
        agent_name="worker",
        agent_kind="worker",
    )
    agent_run = AgentRunModel(
        run_id=uuid4(),
        agent_id=agent.agent_id,
        agent_kind="worker",
        workspace_id=uuid4(),
    )

    snapshot = RuntimeSnapshotResolver().resolve(agent_run, agent)

    assert snapshot["skill_config"] == {
        "builtins_enabled": True,
        "paths": [],
        "include_global": False,
        "allowed_skills": [],
    }
    assert snapshot["mcp_config"] == {
        "enabled": False,
        "servers": [],
    }
```

- [ ] **Step 2: Run the focused snapshot test and verify failure**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py::test_runtime_snapshot_includes_skill_and_mcp_config_defaults -v`

Expected: FAIL with missing `skill_config` / `mcp_config` keys or `AgentModel` validation error for unknown fields.

- [ ] **Step 3: Add minimal config model files**

Create `app/models/agent_skill_config.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class AgentSkillConfig(BaseModel):
    builtins_enabled: bool = True
    paths: list[str] = Field(default_factory=list)
    include_global: bool = False
    allowed_skills: list[str] = Field(default_factory=list)
```

Create `app/models/agent_mcp_config.py`:

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentMcpServerConfig(BaseModel):
    name: str
    enabled: bool = True
    type: str
    preset: str | None = None
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: int | None = None
    command: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)


class AgentMcpConfig(BaseModel):
    enabled: bool = False
    servers: list[AgentMcpServerConfig] = Field(default_factory=list)
```

- [ ] **Step 4: Wire the new configs into `AgentModel` and runtime snapshot**

Update `app/models/agent.py` imports and fields:

```python
from app.models.agent_mcp_config import AgentMcpConfig
from app.models.agent_skill_config import AgentSkillConfig


class AgentModel(BaseModel):
    ...
    tool_config: AgentToolsetConfig = Field(default_factory=AgentToolsetConfig)
    skill_config: AgentSkillConfig = Field(default_factory=AgentSkillConfig)
    mcp_config: AgentMcpConfig = Field(default_factory=AgentMcpConfig)
    executor_config: AgentExecutorConfig = Field(default_factory=AgentExecutorConfig)
    ...
```

Update `app/runtime/snapshot/runtime_snapshot_resolver.py`:

```python
snapshot.setdefault("skill_config", agent.skill_config.model_dump())
snapshot.setdefault("mcp_config", agent.mcp_config.model_dump())
```

And in `build_default_snapshot()`:

```python
"skill_config": agent.skill_config.model_dump(),
"mcp_config": agent.mcp_config.model_dump(),
```

- [ ] **Step 5: Re-run the focused snapshot test and verify pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py::test_runtime_snapshot_includes_skill_and_mcp_config_defaults -v`

Expected: PASS

---

### Task 2: Add Runtime Bundle Fields And Runtime Resolvers

**Files:**
- Create: `app/runtime/skills/resolver.py`
- Create: `app/runtime/mcp/resolver.py`
- Modify: `app/runtime/runtime_assembler.py`
- Test: `tests/test_runtime_skill_resolver.py`
- Test: `tests/test_runtime_mcp_resolver.py`
- Modify: `tests/test_instruction_resolver.py`

- [ ] **Step 1: Write failing runtime resolver tests**

Create `tests/test_runtime_skill_resolver.py`:

```python
from app.runtime.skills.resolver import SkillRuntimeResolver


def test_skill_runtime_resolver_builds_registry_from_snapshot(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    skill_dir = workspace / ".agenthub" / "skills" / "local-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: local-skill\ndescription: local test skill\n---\n\n# Local Skill\n",
        encoding="utf-8",
    )

    runtime = SkillRuntimeResolver().resolve(
        workspace_root=str(workspace),
        skill_config={"builtins_enabled": False, "paths": [str(workspace / ".agenthub" / "skills")], "include_global": False, "allowed_skills": []},
    )

    assert runtime.get("local-skill")["name"] == "local-skill"
```
```

Create `tests/test_runtime_mcp_resolver.py`:

```python
from app.runtime.mcp.resolver import McpRuntimeResolver


def test_mcp_runtime_resolver_returns_disabled_runtime_by_default() -> None:
    runtime = McpRuntimeResolver().resolve({"enabled": False, "servers": []})

    assert runtime["enabled"] is False
    assert runtime["tools"] == []
```
```

- [ ] **Step 2: Run the focused runtime resolver tests and verify failure**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_skill_resolver.py tests/test_runtime_mcp_resolver.py -v`

Expected: FAIL with import errors for missing resolver modules.

- [ ] **Step 3: Add minimal runtime resolver files**

Create `app/runtime/skills/resolver.py`:

```python
from __future__ import annotations

from app.skills.registry import SkillRegistry


class SkillRuntimeResolver:
    def __init__(self, registry: SkillRegistry | None = None) -> None:
        self.registry = registry or SkillRegistry()

    def resolve(self, *, workspace_root: str, skill_config: dict[str, object]) -> SkillRegistry:
        return self.registry.build(workspace_root=workspace_root, skill_config=skill_config)
```

Create `app/runtime/mcp/resolver.py`:

```python
from __future__ import annotations

from app.mcp.service import McpService


class McpRuntimeResolver:
    def __init__(self, service: McpService | None = None) -> None:
        self.service = service or McpService()

    def resolve(self, mcp_config: dict[str, object]) -> dict[str, object]:
        return self.service.build_runtime(mcp_config)
```

- [ ] **Step 4: Extend `RuntimeBundle` and `RuntimeAssembler`**

Update `app/runtime/runtime_assembler.py` dataclass fields:

```python
skill_config: dict[str, Any] = field(default_factory=dict)
mcp_config: dict[str, Any] = field(default_factory=dict)
skill_registry: Any | None = None
mcp_runtime: dict[str, Any] = field(default_factory=dict)
```

Update constructor dependencies:

```python
from app.runtime.mcp.resolver import McpRuntimeResolver
from app.runtime.skills.resolver import SkillRuntimeResolver

...
self.skill_runtime_resolver = skill_runtime_resolver or SkillRuntimeResolver()
self.mcp_runtime_resolver = mcp_runtime_resolver or McpRuntimeResolver()
```

Update `assemble()`:

```python
skill_config = dict(runtime_snapshot.get("skill_config") or {})
mcp_config = dict(runtime_snapshot.get("mcp_config") or {})
skill_registry = self.skill_runtime_resolver.resolve(
    workspace_root=workspace_root,
    skill_config=skill_config,
)
mcp_runtime = self.mcp_runtime_resolver.resolve(mcp_config)
```

and include them in `RuntimeBundle(...)`.

- [ ] **Step 5: Update helper tests to pass new runtime bundle fields**

Update `tests/test_instruction_resolver.py` helper:

```python
        skill_config={"builtins_enabled": True, "paths": [], "include_global": False, "allowed_skills": []},
        mcp_config={"enabled": False, "servers": []},
        skill_registry=None,
        mcp_runtime={"enabled": False, "tools": []},
```

- [ ] **Step 6: Re-run the focused runtime resolver tests and verify pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_skill_resolver.py tests/test_runtime_mcp_resolver.py tests/test_instruction_resolver.py -v`

Expected: PASS

---

### Task 3: Implement Skills Registry And Prompt Exposure

**Files:**
- Create: `app/skills/registry.py`
- Modify: `app/runtime/prompt/prompt_composer.py`
- Test: `tests/test_skill_registry.py`
- Modify: `tests/test_instruction_resolver.py`

- [ ] **Step 1: Write failing skill registry and prompt tests**

Create `tests/test_skill_registry.py`:

```python
from app.skills.registry import SkillRegistry


def test_skill_registry_loads_workspace_skill(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    skill_dir = workspace / ".agenthub" / "skills" / "debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: debugging\ndescription: Debug failures\n---\n\n# Debugging\n",
        encoding="utf-8",
    )

    registry = SkillRegistry().build(
        workspace_root=str(workspace),
        skill_config={"builtins_enabled": False, "paths": [str(workspace / ".agenthub" / "skills")], "include_global": False, "allowed_skills": []},
    )

    assert registry.get("debugging")["description"] == "Debug failures"


def test_skill_registry_renders_available_skills_block(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    skill_dir = workspace / ".agenthub" / "skills" / "debugging"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: debugging\ndescription: Debug failures\n---\n\n# Debugging\n",
        encoding="utf-8",
    )

    registry = SkillRegistry().build(
        workspace_root=str(workspace),
        skill_config={"builtins_enabled": False, "paths": [str(workspace / ".agenthub" / "skills")], "include_global": False, "allowed_skills": []},
    )

    rendered = registry.render_available_skills()

    assert "<available_skills>" in rendered
    assert "<name>debugging</name>" in rendered
```
```

Append to `tests/test_instruction_resolver.py` or add `tests/test_prompt_composer.py` coverage:

```python
def test_prompt_composer_includes_available_skills_block(tmp_path) -> None:
    runtime = _build_runtime_bundle(str(tmp_path))
    runtime.skill_registry = type(
        "FakeSkillRegistry",
        (),
        {"render_available_skills": lambda self: "<available_skills><skill><name>debugging</name><description>Debug failures</description></skill></available_skills>"},
    )()

    prompt = PromptComposer().compose(runtime, InputEventModel(type=InputEventType.USER_INPUT, payload={"content": "hi"}, input_id=uuid4(), run_id=runtime.agent_run.run_id, idempotency_key="k"))

    assert "<available_skills>" in prompt.system_prompt
```
```

- [ ] **Step 2: Run focused skills tests and verify failure**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_skill_registry.py tests/test_instruction_resolver.py -v`

Expected: FAIL with missing `app.skills.registry` module and missing prompt section.

- [ ] **Step 3: Implement minimal `SkillRegistry`**

Create `app/skills/registry.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(slots=True)
class SkillRegistry:
    skills: dict[str, dict[str, str]]

    def __init__(self, skills: dict[str, dict[str, str]] | None = None) -> None:
        self.skills = skills or {}

    def build(self, *, workspace_root: str, skill_config: dict[str, object]) -> "SkillRegistry":
        skills: dict[str, dict[str, str]] = {}
        for root in skill_config.get("paths", []):
            self._load_from_root(skills, Path(str(root)))
        return SkillRegistry(skills)

    def all(self) -> list[dict[str, str]]:
        return list(self.skills.values())

    def available(self) -> list[dict[str, str]]:
        return [item for item in self.all() if item.get("description")]

    def get(self, name: str) -> dict[str, str]:
        return self.skills[name]

    def render_available_skills(self) -> str:
        items = [
            "<available_skills>",
            *[
                "  <skill>\n"
                f"    <name>{item['name']}</name>\n"
                f"    <description>{item['description']}</description>\n"
                "  </skill>"
                for item in sorted(self.available(), key=lambda item: item["name"])
            ],
            "</available_skills>",
        ]
        return "\n".join(items) if len(items) > 2 else ""

    def _load_from_root(self, skills: dict[str, dict[str, str]], root: Path) -> None:
        if not root.exists():
            return
        for path in root.glob("*/SKILL.md"):
            content = path.read_text(encoding="utf-8")
            match = re.match(r"---\nname:\s*(?P<name>[^\n]+)\ndescription:\s*(?P<description>[^\n]+)\n---\n\n(?P<body>.*)", content, re.DOTALL)
            if not match:
                continue
            name = match.group("name").strip()
            skills[name] = {
                "name": name,
                "description": match.group("description").strip(),
                "content": match.group("body").strip(),
                "location": str(path),
            }
```

- [ ] **Step 4: Inject available skills into the system prompt**

Update `app/runtime/prompt/prompt_composer.py`:

```python
            self._build_skill_section(runtime),
```

and add:

```python
    def _build_skill_section(self, runtime: RuntimeBundle) -> PromptSection | None:
        registry = getattr(runtime, "skill_registry", None)
        if registry is None:
            return None
        rendered = registry.render_available_skills()
        if not rendered:
            return None
        return self._section(
            "skills",
            "runtime",
            "Skills provide specialized instructions and workflows for specific tasks.\n"
            "Use the skill tool to load a skill when a task matches its description.\n\n"
            f"{rendered}",
        )
```

- [ ] **Step 5: Re-run focused skills tests and verify pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_skill_registry.py tests/test_instruction_resolver.py tests/test_prompt_composer.py -v`

Expected: PASS

---

### Task 4: Add Skill Tool And Tool Resolver Integration

**Files:**
- Create: `app/tools/skill_tool.py`
- Create: `app/schemas/skill_tool.py`
- Modify: `app/runtime/tools/tool_resolver.py`
- Test: `tests/test_skill_tool.py`
- Modify: `tests/test_tool_resolver.py`

- [ ] **Step 1: Write failing skill tool tests**

Create `tests/test_skill_tool.py`:

```python
from app.tools.skill_tool import SkillTool


class SkillRequest:
    name = "debugging"


def test_skill_tool_loads_skill_from_runtime_registry() -> None:
    runtime = type(
        "Runtime",
        (),
        {"skill_registry": type("Registry", (), {"get": lambda self, name: {"name": name, "description": "Debug failures", "content": "# Debugging", "location": "built-in"}})()},
    )()

    result = SkillTool().run(runtime=runtime, request=SkillRequest())

    assert result["name"] == "debugging"
    assert "Debug failures" in result["content"]
```

Append to `tests/test_tool_resolver.py`:

```python
def test_tool_resolver_registers_skill_tool_when_enabled() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_config={
            "tools": [{"name": "skill_tool", "enabled": True, "options": {}}],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"provider": "openai_compatible", "model": "gpt-test"},
    )

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert [item.name for item in view.system_tools] == ["skill_tool"]
    assert [item["function"]["name"] for item in view.model_tools] == ["skill_tool"]
```
```

- [ ] **Step 2: Run focused skill tool tests and verify failure**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_skill_tool.py tests/test_tool_resolver.py::test_tool_resolver_registers_skill_tool_when_enabled -v`

Expected: FAIL with import errors for `skill_tool` or missing resolver registration.

- [ ] **Step 3: Add schema and tool implementation**

Create `app/schemas/skill_tool.py`:

```python
from __future__ import annotations

from pydantic import BaseModel


class SkillToolRequest(BaseModel):
    name: str


def build_skill_tool_definition() -> dict[str, object]:
    return {
        "type": "function",
        "function": {
            "name": "skill_tool",
            "description": "Load a skill by name from the available_skills list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    }
```

Create `app/tools/skill_tool.py`:

```python
from __future__ import annotations


class SkillTool:
    def run(self, *, runtime, request):
        skill = runtime.skill_registry.get(request.name)
        return {
            "name": skill["name"],
            "content": (
                f"<skill_content name=\"{skill['name']}\">\n"
                f"description: {skill['description']}\n\n"
                f"{skill['content']}\n\n"
                f"location: {skill['location']}\n"
                "</skill_content>"
            ),
        }
```

- [ ] **Step 4: Register `skill_tool` in `ToolResolver`**

Update `app/runtime/tools/tool_resolver.py` imports and registration:

```python
from app.schemas.skill_tool import SkillToolRequest, build_skill_tool_definition
from app.tools.skill_tool import SkillTool
```

Add branch:

```python
        if tool_name == "skill_tool":
            registry.register(
                ToolSpec(
                    name="skill_tool",
                    tool=SkillTool(),
                    definition=build_skill_tool_definition(),
                    request_model=SkillToolRequest,
                    invoke=default_invoke,
                )
            )
            return
```

- [ ] **Step 5: Re-run focused skill tool tests and verify pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_skill_tool.py tests/test_tool_resolver.py::test_tool_resolver_registers_skill_tool_when_enabled -v`

Expected: PASS

---

### Task 5: Add MCP Service And Dynamic MCP Tool Registration

**Files:**
- Create: `app/mcp/service.py`
- Modify: `app/runtime/mcp/resolver.py`
- Modify: `app/runtime/tools/tool_resolver.py`
- Test: `tests/test_mcp_service.py`
- Modify: `tests/test_tool_resolver.py`

- [ ] **Step 1: Write failing MCP service and tool resolver tests**

Create `tests/test_mcp_service.py`:

```python
from app.mcp.service import McpService


def test_mcp_service_build_runtime_returns_disabled_shape() -> None:
    runtime = McpService().build_runtime({"enabled": False, "servers": []})

    assert runtime == {"enabled": False, "tools": []}


def test_mcp_service_normalizes_tool_names() -> None:
    service = McpService()
    specs = service.build_tool_specs(
        server_name="github",
        tools=[{"name": "search issues", "description": "Search GitHub issues", "input_schema": {"type": "object", "properties": {}}}],
    )

    assert specs[0].name == "github__search_issues"
```

Append to `tests/test_tool_resolver.py`:

```python
def test_tool_resolver_merges_mcp_runtime_tools() -> None:
    runtime = _build_runtime_bundle(
        role="worker",
        tool_config={
            "tools": [{"name": "code_tool", "enabled": True, "options": {}}],
            "model_tools_enabled": True,
            "runtime_tools_enabled": True,
            "auto_tool_choice": True,
        },
        executor_config={"provider": "openai_compatible", "model": "gpt-test"},
    )
    runtime.mcp_runtime = {
        "enabled": True,
        "tools": [
            ToolSpec(
                name="github__search_issues",
                tool=object(),
                definition={"type": "function", "function": {"name": "github__search_issues", "description": "Search issues", "parameters": {"type": "object", "properties": {}}}},
                request_model=dict,
                invoke=lambda tool, runtime, request: {"ok": True},
            )
        ],
    }

    view = ToolResolver(PlanRepository()).resolve(runtime)

    assert "github__search_issues" in [item.name for item in view.system_tools]
```
```

- [ ] **Step 2: Run focused MCP tests and verify failure**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_mcp_service.py tests/test_tool_resolver.py::test_tool_resolver_merges_mcp_runtime_tools -v`

Expected: FAIL with missing `app.mcp.service` or missing MCP merge path.

- [ ] **Step 3: Implement minimal `McpService`**

Create `app/mcp/service.py`:

```python
from __future__ import annotations

from app.runtime.tools.tool_registry import ToolSpec


def _invoke_mcp_tool(tool: object, runtime, request):
    return tool.run(request)


class _StaticMcpTool:
    def __init__(self, definition: dict[str, object]) -> None:
        self.definition = definition

    def run(self, request):
        return {"request": request, "definition": self.definition}


class McpService:
    def build_runtime(self, mcp_config: dict[str, object]) -> dict[str, object]:
        if not mcp_config.get("enabled"):
            return {"enabled": False, "tools": []}

        tool_specs = []
        for server in mcp_config.get("servers", []):
            if not server.get("enabled", True):
                continue
            tool_specs.extend(self.build_tool_specs(server_name=server["name"], tools=server.get("tools", [])))
        return {"enabled": True, "tools": tool_specs}

    def build_tool_specs(self, *, server_name: str, tools: list[dict[str, object]]) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        for item in tools:
            normalized = item["name"].replace(" ", "_")
            tool_name = f"{server_name}__{normalized}"
            definition = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": item.get("description", ""),
                    "parameters": item.get("input_schema", {"type": "object", "properties": {}}),
                },
            }
            specs.append(
                ToolSpec(
                    name=tool_name,
                    tool=_StaticMcpTool(definition),
                    definition=definition,
                    request_model=dict,
                    invoke=_invoke_mcp_tool,
                )
            )
        return specs
```

- [ ] **Step 4: Merge MCP runtime tools inside `ToolResolver`**

Update `app/runtime/tools/tool_resolver.py` after built-in registration loop:

```python
        for spec in runtime.mcp_runtime.get("tools", []):
            registry.register(spec)
```

- [ ] **Step 5: Re-run focused MCP tests and verify pass**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_mcp_service.py tests/test_tool_resolver.py::test_tool_resolver_merges_mcp_runtime_tools -v`

Expected: PASS

---

### Task 6: Run Regression Suite For Runtime, Tools, MCP, And Skills

**Files:**
- Modify: `tests/test_tool_resolver.py`
- Modify: `tests/test_runtime_policy_resolvers.py`
- Modify: `tests/test_instruction_resolver.py`
- Modify: `tests/test_prompt_composer.py`
- Test: `tests/test_runtime_skill_resolver.py`
- Test: `tests/test_runtime_mcp_resolver.py`
- Test: `tests/test_skill_registry.py`
- Test: `tests/test_skill_tool.py`
- Test: `tests/test_mcp_service.py`

- [ ] **Step 1: Add final combined assertions for runtime bundle defaults and tool visibility**

Make sure the final assertions exist:

```python
assert runtime_bundle.skill_config == {
    "builtins_enabled": True,
    "paths": [],
    "include_global": False,
    "allowed_skills": [],
}
assert runtime_bundle.mcp_runtime["enabled"] is False
assert "skill_tool" in [item["function"]["name"] for item in runtime_bundle.tool_view.model_tools]
```

- [ ] **Step 2: Run the focused runtime-and-tools suite**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py tests/test_runtime_skill_resolver.py tests/test_runtime_mcp_resolver.py tests/test_instruction_resolver.py tests/test_prompt_composer.py tests/test_tool_resolver.py tests/test_skill_registry.py tests/test_skill_tool.py tests/test_mcp_service.py -v`

Expected: PASS

- [ ] **Step 3: Run the broader regression suite for existing tool-chain safety**

Run: `& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_runtime_policy_resolvers.py tests/test_runtime_assembler.py tests/test_tool_resolver.py tests/test_prompt_composer.py tests/test_instruction_resolver.py tests/test_llm_executor.py tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py tests/test_delegate_chain_e2e_internal_llm.py tests/test_code_tool.py tests/test_bash_tool.py tests/test_plan_tool.py tests/test_tool_call_handler.py -v`

Expected: PASS

- [ ] **Step 4: Record any failing test names before fixing anything else**

If any failures appear, capture the exact failing node ids first. Example format:

```text
tests/test_prompt_composer.py::test_prompt_composer_includes_available_skills_block
tests/test_tool_resolver.py::test_tool_resolver_merges_mcp_runtime_tools
```

Do not start opportunistic refactors. Fix only failures that are directly caused by MCP/skills runtime changes.

---

## Self-Review Checklist

- Spec coverage:
  - `app/mcp/service.py`: covered by Task 5
  - `app/skills/registry.py`: covered by Task 3
  - `app/runtime/mcp/resolver.py`: covered by Task 2
  - `app/runtime/skills/resolver.py`: covered by Task 2
  - `skill_tool`: covered by Task 4
  - prompt `available_skills`: covered by Task 3
  - dynamic MCP tool registration: covered by Task 5
  - runtime snapshot / bundle plumbing: covered by Tasks 1 and 2
  - regression verification: covered by Task 6
- Placeholder scan:
  - No `TODO` / `TBD` / “similar to above” placeholders remain.
- Type consistency:
  - Uses `skill_config`, `mcp_config`, `skill_registry`, and `mcp_runtime` consistently across tasks.

## Notes For Execution

- Follow TDD strictly within each task: write the failing test first, then the minimal implementation, then rerun the targeted test.
- Do not migrate `app/tools/` or `app/runtime/tools/` as part of this plan.
- Do not add `app/mcp/models.py`, `app/mcp/client.py`, `app/skills/discovery.py`, or `app/skills/formatter.py` in this iteration.
- Keep changes minimal and local to the feature.
- User preference from the current conversation: avoid step-by-step process commits; prefer a single final commit after verification.
