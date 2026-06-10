# Bash Tool E2E Extension Design

## Summary

This design extends the newly added `bash_tool` from runtime/tool-level coverage to agent-level end-to-end coverage.

The extension has two goals:

- permanently expose `bash_tool` to orchestrator runs in `orchestrator_default`
- validate two agentic chains end to end:
  - orchestrator uses `bash_tool` to inspect workspace state before creating or updating a plan
  - delegated worker uses `bash_tool` to move a file inside the workspace

The purpose is not just to test the tool in isolation. The purpose is to prove that internal agents can see the tool, choose it, execute it, and complete the surrounding orchestration flow.

## Goals

- Add `bash_tool` to `orchestrator_default` permanently.
- Preserve `bash_tool` in `worker_default`.
- Add prompt guidance so orchestrators and workers actually use `bash_tool` when command execution is required.
- Add scripted delegate-chain coverage for worker file moves.
- Add real internal LLM E2E coverage for orchestrator `bash_tool` usage and worker `bash_tool` usage.
- Keep the extension aligned with the existing `code_tool` E2E testing style.

## Non-Goals

- No redesign of `bash_tool` execution internals.
- No new shell permission model beyond the current `command_policies` behavior.
- No expansion into interactive shell sessions.
- No attempt to make `code_tool` and `bash_tool` interchangeable in tests.
- No temporary test-only tool exposure path for orchestrators.

## Current State

Current behavior after the initial `bash_tool` implementation:

- `worker_default` exposes `code_tool` and `bash_tool`
- `orchestrator_default` exposes `plan_tool` and `delegate_tool` only
- `worker_mode_prompt` explicitly tells workers to use `code_tool` for file writes
- there is no orchestrator prompt guidance for command-based inspection
- `bash_tool` has runtime-level and tool-level tests, but not agent-level E2E tests

The existing `code_tool` tests provide the exact pattern to extend:

- scripted delegate-chain test using a sequenced executor
- real internal LLM E2E using a recording wrapper around the real executor

## Design Principles

- Keep the new coverage close to the proven `code_tool` E2E pattern.
- Expose `bash_tool` in production runtime configuration, not only in tests.
- Validate actual tool choice, not just final file system state.
- Keep each E2E test focused on one primary tool behavior.
- Reuse the real workspace under `.AgentHub/tests/` for file-move assertions.

## Proposed Changes

### 1. Permanently expose `bash_tool` to orchestrators

`orchestrator_default` should register `bash_tool` alongside `plan_tool` and `delegate_tool`.

Expected orchestrator system toolset after this change:

- `plan_tool`
- `delegate_tool`
- `bash_tool`

This is a real runtime contract change, not a test-only override.

Rationale:

- the orchestrator chain you requested requires direct command inspection before planning
- a permanent default is simpler and more honest than hidden test configuration
- it keeps runtime behavior aligned with expected agent responsibilities

### 2. Add prompt guidance for command-backed planning and file moves

The current prompts are too narrow:

- worker prompt only mentions `code_tool` for file mutation
- orchestrator prompt says only that the orchestrator is responsible for planning

Required prompt updates:

- `orchestrator_mode_prompt`
  - when planning depends on file listings, file contents reachable through shell commands, or other command-line inspection, the orchestrator must call `bash_tool` rather than assume command output in plain text
- `worker_mode_prompt`
  - keep the existing `code_tool` rule for direct file edits
  - add a narrow rule that when a task explicitly requires shell-based file relocation, copy, or rename operations, the worker should use `bash_tool`

This keeps the behavioral split clear:

- edit/create/delete file contents -> `code_tool`
- shell inspection or shell-driven file moves -> `bash_tool`

### 3. Add scripted delegate-chain coverage for worker file moves

Add a deterministic test parallel to `test_delegate_chain_internal_code_tool.py`.

Scenario:

- orchestrator creates a plan
- orchestrator delegates a task to a worker
- worker uses `bash_tool` to move a file from `.AgentHub/tests/test1/bash_tool_test1.md` to `.AgentHub/tests/test2/bash_tool_test1.md`
- orchestrator receives callback and completes the plan

Assertions:

- worker visible tools include `bash_tool`
- worker response tool calls include `bash_tool`
- source file no longer exists
- target file exists
- target file content remains `test`
- orchestrator run completes
- worker run completes
- orchestrator plan completes

This test should stay scripted so it proves the runtime/tool dispatch chain deterministically.

### 4. Add real internal LLM E2E for orchestrator `bash_tool` usage

Add a real internal LLM E2E test parallel to `test_delegate_chain_e2e_internal_llm.py`.

Scenario:

- orchestrator receives a user prompt instructing it to inspect a known workspace file or directory via `bash_tool`
- the prompt explicitly forbids claiming inspection results without calling the tool
- after inspecting, the orchestrator creates or updates a one-step plan with `plan_tool`

Assertions:

- orchestrator visible tools include `bash_tool`
- orchestrator response tool calls include `bash_tool`
- a later orchestrator response includes `plan_tool`
- resulting plan file exists on disk
- run finishes completed

This test proves direct orchestrator `bash_tool` adoption under the real internal LLM path.

### 5. Add real internal LLM E2E for delegated worker `bash_tool` usage

Add a second real internal LLM E2E for file relocation.

Scenario:

- orchestrator creates a plan and delegates to a worker
- worker prompt explicitly requires using `bash_tool` to move the file
- worker uses `bash_tool` to move `.AgentHub/tests/test1/bash_tool_test1.md` into `.AgentHub/tests/test2/`
- orchestrator receives callback and completes the plan

Assertions:

- worker visible tools include `bash_tool`
- worker response tool calls include `bash_tool`
- source file is removed
- target file exists with preserved content
- orchestrator callback cycle completes

This test is the closest `bash_tool` analogue to the existing `code_tool` internal LLM E2E.

## Data Flow

### Orchestrator inspection path

1. user input arrives
2. orchestrator runtime exposes `plan_tool`, `delegate_tool`, and `bash_tool`
3. orchestrator prompt instructs tool-backed inspection when command results are needed
4. model calls `bash_tool`
5. tool result returns to orchestrator
6. model calls `plan_tool`
7. plan persists to `.AgentHub/plans/...`

### Delegated worker file-move path

1. orchestrator receives user input
2. orchestrator creates plan and delegates
3. worker runtime exposes `code_tool` and `bash_tool`
4. worker prompt plus delegated task require shell-based file move
5. model calls `bash_tool`
6. source file moves to target path
7. callback returns to orchestrator
8. orchestrator updates plan to completed

## Testing Strategy

### Runtime and visibility tests

Update existing tests to reflect the new orchestrator default toolset:

- orchestrator runtime assembler tests
- tool resolver tests

These tests must now expect `bash_tool` in orchestrator-visible runtime tools.

### Scripted chain test

Add one deterministic delegate-chain test for worker file moves.

Purpose:

- verify runtime dispatch and callback handling without relying on live model behavior

### Real internal LLM E2E tests

Add two opt-in real tests gated by existing provider settings:

- orchestrator command-inspection then planning
- worker file move via delegate flow

Purpose:

- verify real model tool selection and end-to-end completion

## Risks And Mitigations

### Risk: orchestrator may ignore `bash_tool` and answer from prior knowledge

Mitigation:

- strengthen orchestrator prompt wording
- make the test prompt explicitly forbid text-only assumptions
- assert actual `response_tool_calls` includes `bash_tool`

### Risk: worker may choose `code_tool` or plain text instead of `bash_tool`

Mitigation:

- make the delegated task explicitly require shell-based move semantics
- add prompt wording that shell-based relocation should use `bash_tool`
- assert worker tool calls include `bash_tool`

### Risk: changing orchestrator default toolset breaks existing tests

Mitigation:

- update existing orchestrator visibility assertions in the same change set
- run broad runtime regressions after the E2E additions

## Recommended Scope

This extension should include:

- permanent orchestrator exposure of `bash_tool`
- prompt updates for orchestrator and worker modes
- one scripted worker file-move delegate test
- one real orchestrator `bash_tool` inspection E2E
- one real worker `bash_tool` move E2E
- updated resolver/runtime tests for orchestrator tool visibility

This extension should not include:

- additional `bash_tool` feature work unrelated to E2E coverage
- new permission concepts
- interactive shell session behavior
