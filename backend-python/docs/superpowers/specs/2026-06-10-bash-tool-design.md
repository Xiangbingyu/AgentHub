# Bash Tool Design

## Summary

This design adds a runtime-visible `bash_tool` for internal worker agents. The tool executes shell commands inside the session workspace, integrates with the existing `tool_policy` and runtime policy pipeline, and keeps command execution separate from `workspace_session` file access.

The first version is intentionally not a full shell parser. It uses a lightweight preflight stage to validate working directory constraints, derive command-prefix patterns for policy checks, and reject clearly disallowed execution before launching a subprocess.

## Goals

- Add a normal runtime tool named `bash_tool` for command execution.
- Bind command execution to the current session `workspace_root` by default.
- Route authorization through the existing `tool_policy` and runtime policy system.
- Support basic command-pattern rules such as `git *`, `git push *`, `pytest *`, and `rm *`.
- Provide stable structured results with exit code, timeout, abort, and truncation metadata.
- Keep the design small enough to implement without introducing a large shell parsing subsystem.

## Non-Goals

- No migration of shell execution into `workspace_session`.
- No interactive terminal session management or persistent shell state.
- No full AST-level path extraction like `opencode` in the first version.
- No external directory permission system in the first version.
- No streaming terminal UI or incremental metadata updates in the first version.
- No git-specific abstraction layer.

## Context

The current backend already has the main pieces needed for this feature:

- `RuntimeAssembler` resolves and injects `workspace_root`.
- `RuntimeBundle` is already passed into generic tool execution.
- `tool_policy` and runtime prompt/policy resolution already exist.
- `code_tool` and `plan_tool` now use the shared workspace model through `workspace_session`.

This means `bash_tool` does not need a new runtime framework. It needs one new command-oriented tool, one lightweight preflight layer, and policy integration that matches existing runtime decisions.

## Design Principles

- Keep file access and command execution separate.
- Reuse current runtime wiring instead of introducing a parallel execution path.
- Evaluate policy before subprocess execution.
- Prefer command-prefix matching over raw full-string matching for useful policy rules.
- Keep the first version conservative when parsing is ambiguous.
- Return structured execution results instead of throwing for ordinary non-zero exits.

## Proposed Architecture

### 1. `bash_tool` remains a normal runtime tool

`bash_tool` should be registered and exposed the same way as `code_tool`.

It should live as a standard tool implementation under `app/tools/` with a matching schema under `app/schemas/`.

Expected placement:

- `app/tools/bash_tool.py`
- `app/schemas/bash_tool.py`

`ToolResolver` should make it model-visible for internal worker runs.

### 2. `workspace_session` is not extended for commands

`workspace_session` remains a file access capability only.

`bash_tool` should use:

- `runtime.workspace_root` as the default working directory
- runtime policy state for permission checks
- tool invocation context for run metadata

This preserves the boundary established in the earlier workspace design:

- file IO goes through `workspace_session`
- command execution goes through `bash_tool`

### 3. Add a lightweight preflight stage before execution

Before running a subprocess, `bash_tool` should perform a small preflight pass that:

1. validates input
2. resolves the effective `cwd`
3. derives policy patterns from the command string
4. checks the command against the active `tool_policy`

This preflight is the first version's safety boundary. It is intentionally smaller than `opencode`'s AST-based scanning, but it creates a clean extension point for future improvements.

### 4. Keep execution synchronous from the runtime's perspective

The first version should execute the command, collect output, apply truncation, and return one structured result.

It should not try to emulate a live terminal stream or maintain a persistent shell session. That would add UI and lifecycle complexity without improving the core runtime boundary that needs to be validated first.

## Interface

### Tool parameters

The first version should keep the input surface minimal:

```python
{
    "command": "pytest tests/test_code_tool.py -v",
    "description": "Runs code tool tests",
    "timeout": 120000,
    "workdir": "tests",
}
```

Field semantics:

- `command`: required raw shell command string
- `description`: required short human-readable description
- `timeout`: optional timeout in milliseconds, defaults from runtime/config
- `workdir`: optional working directory, relative to `workspace_root` unless absolute and still inside workspace

### Tool result

The tool should return structured output:

```python
{
    "title": "Runs code tool tests",
    "output": "...command output...",
    "metadata": {
        "exit_code": 0,
        "timed_out": False,
        "aborted": False,
        "truncated": False,
        "cwd": "E:/Github/AgentHub-weon/backend-python/tests",
        "command": "pytest tests/test_code_tool.py -v",
    },
}
```

Optional metadata may include:

- `stdout`
- `stderr`
- `output_path` if large output is persisted in a later phase

The exact payload should align with the current tool output conventions already used by runtime tools.

## Working Directory Rules

`bash_tool` must not rely on ambient process `cwd`.

Resolution rules:

- if `workdir` is omitted, use `runtime.workspace_root`
- if `workdir` is relative, resolve it against `runtime.workspace_root`
- if `workdir` is absolute, allow it only if it is contained within `runtime.workspace_root`
- if resolved `cwd` escapes the workspace, reject the call before execution

This mirrors the containment model already established for workspace file access while keeping command execution separate.

## Preflight Pattern Extraction

The first version uses command-prefix matching instead of full shell parsing.

### Purpose

The goal of pattern extraction is to support practical policy rules such as:

- `git *` allow
- `git push *` deny
- `pytest *` allow
- `rm *` deny

This is more useful than checking only whether the tool name is `bash_tool`, and much smaller than implementing a full shell grammar.

### Pattern strategy

The preflight stage should:

1. split simple multi-command strings conservatively on common connectors such as `&&`, `||`, and `;`
2. tokenize each resulting segment with a lightweight shell-aware tokenizer or a conservative fallback
3. derive command-prefix patterns from the leading tokens
4. evaluate each derived pattern against `tool_policy`

Examples:

- `git status --short` -> `git status *`
- `pytest tests/test_code_tool.py -v` -> `pytest *`
- `echo foo && git diff --stat` -> `echo *`, `git diff *`

When parsing is ambiguous, the tool should fall back to a stricter policy input, such as the full trimmed segment, rather than assume the command is safe.

### Why not full AST parsing now

`opencode` uses a much richer shell scan that supports path extraction, shell-specific parsing, and external directory permission checks. That architecture is sound, but reproducing it in the current Python backend would significantly increase cost and risk for the first version.

The proposed design keeps a dedicated preflight layer so that future evolution remains straightforward:

- first version: command-prefix policy only
- later version: richer tokenization and path extraction
- later version: external directory policy checks if needed

## Policy Integration

`bash_tool` should integrate directly with the existing `tool_policy` and runtime policy pipeline.

### Permission key

Use the existing conceptual permission key `bash`.

This keeps policy naming aligned with `opencode` and avoids inventing a second namespace such as `bash_tool.git`.

### Rule shape

Recommended shape:

- permission/tool key: `bash`
- pattern: command prefix string
- action: allow or deny, with current system behavior for anything unresolved

Examples of intended expressiveness:

- `bash` + `git *` -> allow
- `bash` + `git push *` -> deny
- `bash` + `pytest *` -> allow
- `bash` + `rm *` -> deny

If the current policy system only supports coarse tool-level decisions today, this design requires extending it to accept a tool-specific pattern input for `bash` evaluation.

### Enforcement point

Policy must be checked before subprocess execution.

If any derived pattern resolves to deny, `bash_tool` should reject the request without running the command.

For multi-command input, each derived segment should be evaluated. One denied segment denies the full tool call.

## Execution Model

After preflight approval:

1. launch subprocess with resolved `cwd`
2. pass through a controlled environment
3. enforce timeout
4. observe abort/cancellation from runtime if available
5. capture `stdout` and `stderr`
6. apply truncation limits
7. return structured result

### Shell choice

The implementation should respect the host platform:

- Windows: PowerShell or `cmd.exe`, depending on current backend conventions
- non-Windows: system shell appropriate for the environment

The exact shell selection can remain implementation-specific, but the design must keep it explicit rather than implicit through process-global state.

### Environment

The first version should inherit the current process environment by default unless the current runtime already has a stricter environment injection model.

No user-specified environment overrides are required in the first version.

## Output And Truncation

The tool should return readable output without allowing unbounded memory or response growth.

Recommended first-version behavior:

- capture combined output or capture `stdout` and `stderr` separately, depending on existing runtime conventions
- apply line or byte limits before returning the result
- set `metadata.truncated = true` when limits are exceeded
- include a short visible note in `output` when truncation occurred

If there is no stable shared output-persistence mechanism in the current backend, the first version should truncate in memory only. A later phase can add output spill-to-disk.

## Error Model

The design should distinguish between four classes of failures.

### 1. Invalid input

Examples:

- empty command
- negative timeout
- invalid or out-of-workspace `workdir`

These should reject the tool call before execution.

### 2. Policy denied

Examples:

- command matches `rm *` deny
- command matches `git push *` deny

These should reject the tool call before execution with a readable policy error.

### 3. Execution failed

Examples:

- subprocess exits with code 1
- command writes failure details to stderr

This should not be treated as a tool crash. The tool call itself succeeds, but the returned metadata indicates non-zero exit.

### 4. Execution interrupted

Examples:

- timeout
- runtime/user abort

These should return structured interruption metadata, not a generic unclassified exception.

## Testing Strategy

The first implementation should cover:

- command executes successfully in `workspace_root`
- relative `workdir` resolves correctly
- absolute `workdir` inside workspace is accepted
- absolute `workdir` outside workspace is rejected
- policy pattern derivation works for simple commands
- multi-command input produces multiple pattern checks
- denied command does not execute subprocess
- non-zero exit code is returned in metadata
- timeout marks the result as interrupted
- large output is truncated
- `bash_tool` is model-visible for worker runs

Where feasible, tests should avoid shell-specific brittle behavior and prefer cross-platform commands or platform-conditional assertions.

## Alternatives Considered

### Minimal no-pattern executor

Rejected because it does not make the existing policy system meaningfully useful for command execution.

### Full `opencode`-style AST scan in the first version

Rejected for now because it would substantially increase implementation complexity, especially across Windows shell variants, before the runtime boundary and policy wiring are proven.

## Migration And Future Evolution

This design is intentionally staged.

Possible future upgrades:

- richer shell tokenization
- path-aware preflight scanning
- external directory permission rules
- persisted large-output files
- streaming command updates
- shell/environment customization controls

The main architectural requirement is that these upgrades extend the preflight and execution internals without changing the top-level runtime contract.

## Recommended Implementation Scope

The first implementation should include:

- `bash_tool` schema and tool implementation
- runtime/tool resolver exposure for internal worker runs
- preflight command-prefix extraction
- policy evaluation through current runtime policy infrastructure
- workspace-contained `workdir` resolution
- subprocess execution with timeout
- structured result metadata
- truncation tests and policy tests

The first implementation should not include:

- full shell AST parsing
- external directory policy
- persistent shell sessions
- shell output streaming UI
