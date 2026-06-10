# External Code Tools Design

## Summary

Replace executor-mode switching for `claude`, `codex`, and `opencode` with explicit runtime tools that are callable by internal LLM agents. All agents continue to use the internal LLM executor. External coding frameworks become normal tools in the same runtime tool system as `plan_tool`, `delegate_tool`, `code_tool`, and `bash_tool`.

This change also replaces the loose `tool_policy` and `executor_policy` agent fields with explicit structured configuration models: `tool_config` and `executor_config`. The new model removes `system_toolset` and requires every enabled tool to be declared explicitly on the agent.

## Goals

- Keep `internal_llm` as the only agent executor mode.
- Expose `claude`, `codex`, and `opencode` as callable runtime tools instead of executor modes.
- Replace `tool_policy` with an explicit `tool_config` model.
- Replace `executor_policy` with an explicit `executor_config` model.
- Remove `system_toolset`; tool visibility must come only from explicit agent tool declarations.
- Preserve the current runtime shape where orchestrators and workers both remain tool-calling internal LLM agents.
- Reuse as much of the existing framework adapter logic as possible by moving it behind the new tools.

## Non-Goals

- Do not keep backward-compatible dual-write or dual-read support for `tool_policy` and `executor_policy` in the new mainline design.
- Do not retain `framework_cli` as a valid executor mode in the new mainline design.
- Do not type arbitrary custom user-provided OpenAI function definitions in this change.
- Do not change the `bash_tool` behavior introduced in the current branch except where prompt or visibility logic must be adjusted to the new config model.

## Current Problems

The current design mixes two different concepts:

- Agent execution mode is selected through `executor_policy`, including `framework_cli`.
- Agent-callable runtime capabilities are selected through `tool_policy` and system toolset defaults.

That creates avoidable problems:

- `claude`, `codex`, and `opencode` are hidden behind executor switching instead of being explicit capabilities the model can choose.
- `tool_policy` and `executor_policy` are loose dictionaries with weak validation.
- `system_toolset` adds a second source of truth for tool visibility.
- Runtime assembly, prompt composition, and tests have to reason about implicit tool defaults and executor modes at the same time.

## Target Architecture

### Execution Model

All agents use the internal LLM executor.

- `AgentExecutorFactory` always resolves to the internal executor.
- `executor_config` only describes the internal LLM provider configuration.
- External coding frameworks are not executors anymore.

### Tool Model

All runtime capabilities are tools.

Built-in tool names after this change:

- `plan_tool`
- `delegate_tool`
- `code_tool`
- `bash_tool`
- `claude_code_tool`
- `codex_tool`
- `opencode_tool`
- `question_tool`

Tool visibility is driven entirely by explicit agent configuration. There is no `system_toolset` fallback.

### External Code Tool Layer

The existing framework-specific command construction and response parsing logic remains useful, but it moves below the tool layer.

The new layering is:

- `internal_llm` executor drives the agent conversation.
- The model chooses one of the external code tools when it wants external coding help.
- The chosen tool invokes a shared external code runner.
- The runner delegates provider-specific command building and response parsing to the existing adapters.

This keeps provider-specific CLI details out of runtime assembly and keeps the agent loop architecture consistent.

## Data Model

### AgentToolConfig

Each tool is declared explicitly.

```python
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
```

Rules:

- `name` must be one of the built-in tool identifiers.
- `enabled=False` keeps a tool in config without exposing it to the model or runtime registry.
- `options` carries tool-specific runtime settings.

### AgentToolsetConfig

`tool_policy` is replaced by a structured tool config.

```python
class AgentToolsetConfig(BaseModel):
    tools: list[AgentToolConfig] = Field(default_factory=list)
    auto_tool_choice: bool = False
    model_tools_enabled: bool = True
    runtime_tools_enabled: bool = True
```

Rules:

- `tools` is the only source of truth for enabled built-in tools.
- `auto_tool_choice` preserves the existing model tool-choice behavior.
- `model_tools_enabled=False` suppresses tool definitions from model-visible tools.
- `runtime_tools_enabled=False` suppresses runtime tool execution even if a tool is configured.

There is no `system_toolset` field.

### AgentExecutorConfig

`executor_policy` is replaced by a structured executor config.

```python
class AgentExecutorConfig(BaseModel):
    kind: Literal["internal_llm"] = "internal_llm"
    provider: str = "openai_compatible"
    model: str = ""
```

Rules:

- `kind` is fixed to `internal_llm`.
- `provider` and `model` describe the internal LLM backend only.
- No framework CLI fields remain here.

### AgentModel Changes

`AgentModel` becomes:

```python
class AgentModel(BaseModel):
    agent_id: UUID
    agent_name: str
    role: Literal["orchestrator", "worker"] | None = None
    agent_kind: Literal["orchestrator", "worker"] | None = None
    prompt_policy: dict[str, Any] = Field(default_factory=dict)
    tool_config: AgentToolsetConfig = Field(default_factory=AgentToolsetConfig)
    executor_config: AgentExecutorConfig = Field(default_factory=AgentExecutorConfig)
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

`tool_policy` and `executor_policy` are removed from the main model.

## Tool Configuration Semantics

### Default Agent Shapes

Without `system_toolset`, defaults move into explicit agent declarations.

Recommended default orchestrator tools:

- `plan_tool`
- `delegate_tool`
- `bash_tool`

Recommended default worker tools:

- `code_tool`
- `bash_tool`

External coding tools are opt-in for both orchestrators and workers:

- `claude_code_tool`
- `codex_tool`
- `opencode_tool`

If a user wants an orchestrator to call an external code tool directly, they must explicitly include it in `tool_config.tools`.

### External Tool Options

Each external code tool receives its own provider-specific `options` payload.

Recommended baseline options for `claude_code_tool`:

- `command`
- `timeout_seconds`
- `allowed_tools`
- `permission_mode`
- `allow_dangerously_skip_permissions`
- `dangerously_skip_permissions`

Recommended baseline options for `codex_tool`:

- `command`
- `timeout_seconds`
- provider-specific fields already required by the codex adapter

Recommended baseline options for `opencode_tool`:

- `command`
- `timeout_seconds`
- provider-specific fields already required by the opencode adapter

The tool contract should be minimal. The tool input should focus on the task prompt and any per-invocation overrides that are truly needed.

## Runtime Resolution Changes

### Runtime Snapshot

`RuntimeSnapshotResolver` must emit `tool_config` and `executor_config` from the agent and stop producing `tool_policy` and `executor_policy` in the mainline path.

### Runtime Bundle

`RuntimeBundle` should carry:

- `tool_config`
- `executor_config`

It should no longer expose `tool_policy` and `executor_policy` as the primary runtime fields.

### Executor Config Resolution

`ExecutorPolicyResolver` should be replaced or renamed to resolve `executor_config`.

Expected behavior:

- Validate and normalize `executor_config`.
- Default to internal LLM settings when fields are absent.
- Do not interpret framework CLI fields.

### Tool Config Resolution

`ToolPolicyResolver` should be replaced or renamed to resolve `tool_config`.

Expected behavior:

- Validate and normalize the explicit tool list.
- Filter disabled tools.
- Preserve `auto_tool_choice`, `model_tools_enabled`, and `runtime_tools_enabled` behavior.
- Stop deriving tools from `system_toolset`.

### Tool Registry Construction

`ToolResolver` must switch from `system_toolset` branches to explicit registration by configured tool name.

Expected behavior:

- Build an empty registry.
- Iterate configured tools in `tool_config.tools`.
- Register each enabled built-in tool by name.
- Continue exposing model tool definitions only when `model_tools_enabled=True`.
- Continue supporting `tool_choice="auto"` when enabled and model-visible tools exist.

No special executor-mode branch should remain for framework CLI workers.

## External Code Tool Design

### New Runtime Tools

Add three new runtime tools:

- `claude_code_tool`
- `codex_tool`
- `opencode_tool`

Each tool should:

- Validate its request payload with its own schema.
- Resolve tool-level defaults from `AgentToolConfig.options`.
- Invoke a shared external code runner.
- Return normalized structured output for the calling agent.

### Shared External Code Runner

Introduce a shared backend service dedicated to external coding tools.

Responsibilities:

- Accept the current runtime, tool config options, and tool request.
- Resolve the correct framework adapter.
- Build the subprocess command.
- Execute the subprocess inside the workspace root.
- Enforce timeout.
- Normalize failures.
- Parse the response using the selected adapter.

The runner replaces the executor-facing `FrameworkCliExecutor` role, but only as a tool backend.

### Adapter Reuse

Existing adapter classes should remain the provider-specific integration point.

Expected changes:

- Keep `ClaudeCodeAdapter`, `CodexCliAdapter`, and `OpenCodeAdapter`.
- Decouple them from `runtime.executor_policy`.
- Change them to consume explicit tool options and a tool request payload.
- Keep provider-specific command construction and response parsing logic inside the adapter classes.

### Tool Request Shape

All three external coding tools should accept a simple, task-oriented request shape.

Recommended baseline request:

```python
class ExternalCodeToolRequest(BaseModel):
    prompt: str
```

Optional request-level overrides can be added only when justified by a concrete use case. The default should be minimal to keep tool prompts stable and predictable.

## Prompting Changes

Prompt composition must stop referring to implicit system toolsets.

Expected updates:

- `model_visible_tools=` should be derived directly from explicit configured tool names.
- Orchestrator and worker guidance should refer to actual tool visibility, not role-based default assumptions.
- Existing `bash_tool` guidance should remain, but it must apply when `bash_tool` is actually configured.
- New guidance should explain when external code tools are preferable to `code_tool`.

Recommended prompt distinction:

- `code_tool` is for direct workspace file operations.
- `bash_tool` is for shell commands.
- `claude_code_tool` / `codex_tool` / `opencode_tool` are for delegating coding work to external coding frameworks.

## API and Seed Changes

### Agent Creation and Storage

Any code path creating `AgentModel` instances must switch to explicit `tool_config` and `executor_config`.

That includes:

- in-memory seed defaults
- test fixtures
- request schemas if agent creation APIs expose these fields

### Seed Defaults

Seed data should be updated to write explicit tool lists:

- orchestrator seed: `plan_tool`, `delegate_tool`, `bash_tool`
- worker seed: `code_tool`, `bash_tool`

No seed should use `system_toolset`.

## Removal and Cleanup Plan

### Remove from Mainline Runtime

Mainline runtime code should stop depending on:

- `tool_policy`
- `executor_policy`
- `system_toolset`
- `framework_cli` executor mode

### Keep Temporarily Only If Needed for Refactor Safety

If the implementation is done in multiple commits, old classes can remain in the tree temporarily while references are removed. They should not remain wired into the main runtime path.

Examples:

- `FrameworkCliExecutor` may temporarily remain in source while the new shared tool backend is introduced.
- Old tests may temporarily remain until they are replaced.

The final integrated design should not rely on the old mechanism.

## Testing Strategy

This change should be implemented with TDD.

### Unit Tests

Add or update tests for:

- `AgentModel` validation with `tool_config` and `executor_config`
- tool config resolution from explicit tool declarations
- executor config resolution with internal-only semantics
- tool registry construction from explicit tool lists
- each new external code tool request schema and runtime invocation
- shared external code runner command execution and error normalization
- adapter behavior when driven by tool options rather than executor policy

### Runtime Assembly Tests

Update runtime assembly tests to assert:

- `RuntimeBundle` contains `tool_config` and `executor_config`
- explicit configured tool names determine model-visible tools
- no `system_toolset` assumptions remain

### Prompt Tests

Update prompt tests to assert:

- `model_visible_tools` reflects explicit configured tools
- orchestrator and worker prompts mention `bash_tool` only when present
- prompts distinguish `code_tool`, `bash_tool`, and external code tools correctly

### External Tool Flow Tests

Add or update tests to cover:

- worker calling `claude_code_tool`
- worker calling `codex_tool`
- worker calling `opencode_tool`
- orchestrator calling one of these tools when explicitly configured
- interaction between `delegate_tool` and external code tools in internal LLM flows

### Regression Coverage

Preserve regression tests for:

- internal orchestrator tool loop
- `bash_tool` tool visibility and execution
- `code_tool` workspace behavior
- delegate callback flow

## Risks

### Risk: Large Surface Area Change

Replacing both `tool_policy` and `executor_policy` touches many runtime and test files.

Mitigation:

- Make the change in small TDD steps.
- Keep file boundaries focused.
- Land tests for config and resolver changes before external tool integration.

### Risk: Adapter Coupling to Executor Runtime Fields

Existing adapters currently read executor policy fields directly.

Mitigation:

- Introduce a small adapter input object or explicit method arguments for tool options.
- Remove direct dependency on `runtime.executor_policy` from adapter code.

### Risk: Prompt Drift

Prompt guidance can become incorrect if it still assumes role-based default tools.

Mitigation:

- Rebuild prompt tests around explicit configured visibility.
- Gate prompt guidance on actual tool presence.

## Open Decisions Resolved in This Design

The following decisions are fixed by this spec:

- Approach: independent tools with a shared backend
- Executor model: internal LLM only
- Tool configuration: explicit structured `tool_config`
- Executor configuration: explicit structured `executor_config`
- Default tooling: explicit per-agent declarations, no `system_toolset`
- Backward compatibility: old config fields are not part of the new mainline design

## Expected Outcome

After this change:

- every agent is an internal LLM agent
- external coding frameworks are first-class callable tools
- tool visibility is explicit and validated
- executor configuration is narrow and well-defined
- runtime assembly no longer mixes implicit tool defaults with executor mode switching
