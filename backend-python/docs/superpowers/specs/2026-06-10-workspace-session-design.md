# Workspace Session Design

## Summary

This design introduces a minimal `workspace_session` runtime capability that gives tools a shared, session-bound way to read and write files inside the user-defined workspace directory.

The immediate goal is not to add sandboxing. The immediate goal is to stop file-mutating tools from each implementing their own filesystem behavior. `code_tool`, `plan_tool`, and future file-oriented tools should converge on one workspace access path. Command execution remains out of scope for this phase and should be handled later by separate tools such as `bash_tool`.

## Goals

- Keep the current runtime and tool architecture intact.
- Avoid making `code_tool` a special-case tool.
- Introduce a shared file access layer for tools that read or modify workspace files.
- Bind workspace access to the current runtime/session context.
- Leave a clean extension point for future sandboxing without requiring tool rewrites.

## Non-Goals

- No sandbox implementation in this phase.
- No command execution in this phase.
- No git abstraction in this phase.
- No large refactor of the existing tool registry or executor pipeline.
- No immediate rewrite of every existing tool to use the new abstraction in one pass.

## Current State

The existing backend already has a clean runtime assembly pipeline:

`AgentRunInputService -> RuntimeAssembler -> ToolResolver -> ToolRegistry -> tool.run()`

Relevant current behavior:

- `WorkspaceResolver` resolves `workspace_root` from `runtime_snapshot` or settings.
- `RuntimeBundle` already exposes `workspace_root` to the rest of the runtime.
- `worker` runs currently register `code_tool` as a normal runtime tool.
- `plan_tool` currently writes plan files directly using `Path.cwd()` and `Path.write_text()`, not through any shared workspace abstraction.
- Framework executors already use `runtime.workspace_root` as the default current working directory.

This means the system already has a session-bound workspace concept, but it does not yet have a shared filesystem access layer.

## Design Principles

- Keep the best existing structure. Add the smallest missing abstraction instead of redesigning the runtime.
- Keep tools homogeneous. `code_tool`, `plan_tool`, and future tools should remain ordinary tools registered through the same registry model.
- Separate file operations from command execution. File access belongs to workspace capabilities; command execution belongs to future command-oriented tools.
- Centralize path validation and file IO behavior. Tools should not each re-implement root joining, existence checks, or path escape prevention.
- Build for later sandbox adoption by isolating file access behind one runtime capability.

## Proposed Architecture

### 1. Keep `workspace` as the real user directory

`workspace` remains the user-defined real local directory for a session. No copy-on-write layer, temp mirror, or sync mechanism is introduced in this phase.

Responsibilities:

- identify the real directory bound to the current run/session
- expose the root path into runtime state

This remains the job of `WorkspaceResolver`.

### 2. Add `workspace_session` as a runtime capability

Add a thin `WorkspaceSession` object that represents controlled file access for the current runtime.

It is not a new persistence layer and not a sandbox. It is the session-scoped access object between tools and the real workspace.

Responsibilities:

- resolve relative paths against `workspace_root`
- reject paths that escape the workspace root
- provide shared file read/write helpers
- normalize filesystem errors into stable runtime/business errors

### 3. Inject `workspace_session` through `RuntimeBundle`

Extend `RuntimeBundle` with a field such as:

```python
workspace_session: WorkspaceSession | None = None
```

`RuntimeAssembler.assemble()` should:

1. resolve `workspace_root` using the existing resolver
2. construct `WorkspaceSession(workspace_root)`
3. store it on the runtime bundle

This keeps workspace access as a runtime concern, not a tool-local concern.

### 4. Keep tools ordinary; let them consume runtime capabilities

Do not special-case `code_tool` in tool registration.

Instead, let tools that need runtime-bound capabilities receive `runtime` during invocation. This can be done by extending the default invoke path to pass `runtime` into `tool.run(...)` for generic tools.

Example direction:

```python
tool.run(
    run_id=runtime.agent_run.run_id,
    workspace_id=runtime.agent_run.workspace_id,
    runtime=runtime,
    arguments=arguments,
)
```

This preserves the existing registry shape while letting tools opt into runtime services.

### 5. Keep command execution out of this layer

This phase does not put shell execution into `WorkspaceSession`.

Rationale:

- the current goal is code and file read/write only
- command execution is a separate permission and behavior surface
- this matches the opencode model, where file tools and bash are separate built-in tools

Future `bash_tool` or equivalent command tools should reuse the same `workspace_root` as `cwd`, but they do not need to share the same file-operation interface.

## Module Layout

Recommended minimal additions:

- `app/runtime/workspace/workspace_resolver.py`
  - keep as-is for root resolution
- `app/runtime/workspace/workspace_session.py`
  - new session-bound file access object
- `app/runtime/workspace/workspace_errors.py`
  - optional small error module for domain-specific exceptions
- `app/runtime/runtime_assembler.py`
  - inject `workspace_session` into `RuntimeBundle`

This keeps the new behavior close to existing workspace runtime code.

## `WorkspaceSession` Interface

The first phase should keep the API minimal.

Suggested surface:

```python
class WorkspaceSession:
    def __init__(self, workspace_root: str) -> None: ...

    def resolve_path(self, relative_path: str) -> Path: ...
    def exists(self, relative_path: str) -> bool: ...
    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str: ...
    def write_text(
        self,
        relative_path: str,
        content: str,
        *,
        encoding: str = "utf-8",
        overwrite: bool = True,
        create_parent: bool = True,
    ) -> None: ...
    def mkdir(self, relative_path: str, *, parents: bool = True, exist_ok: bool = True) -> None: ...
    def list_dir(self, relative_path: str = ".") -> list[str]: ...
    def delete(self, relative_path: str, *, recursive: bool = False) -> None: ...
```

Notes:

- all tool-facing paths should be relative to `workspace_root`
- absolute paths should be rejected for now to keep semantics simple
- `resolve_path()` should perform canonicalization and root containment checks
- error messages should be stable and readable, not raw OS tracebacks

`apply_patch()` can be added later once there is a concrete consumer. It should not be added early without a tool that needs it.

## Error Model

Expected workspace-layer error categories:

- workspace path escapes root
- file not found
- path already exists when overwrite is false
- target is not a file / target is not a directory
- recursive delete required but not allowed
- invalid relative path input

These can start as small custom exceptions or consistent `ValueError` subclasses. The important part is to centralize them in one layer instead of scattering path and IO failure behavior across tools.

## Tool Integration Strategy

### `code_tool`

`code_tool` remains a normal tool, registered exactly like other runtime tools.

Its difference is only behavioral: it consumes `runtime.workspace_session` to read and write files.

The tool itself should stay focused on translating high-level tool actions into `WorkspaceSession` calls.

Suggested first-step action model:

- `read_file`
- `write_file`
- `list_files`
- `make_dir`
- `delete_path`

Using an action-style payload keeps the tool small while avoiding an explosion of new tool registrations in the first phase.

### `plan_tool`

`plan_tool` is the main proof that shared workspace access is needed.

Today it directly uses:

- `Path.cwd()`
- `path.parent.mkdir(...)`
- `path.write_text(...)`

Target direction:

- preserve its repository behavior and markdown rendering behavior
- move the file write path behind `workspace_session`
- stop relying on ambient process cwd for plan file placement

Migration does not need to happen all at once, but the spec should treat `plan_tool` as a first-class consumer of this shared access path.

### Future `bash_tool`

Future command tools should not reuse the file API directly.

They should, however, reuse the same session/workspace binding and default to the same `workspace_root` for command execution.

This keeps alignment between file tools and command tools without mixing their responsibilities.

## Data Flow

The runtime flow after this design:

1. an agent run is loaded as it is today
2. `RuntimeAssembler` resolves `workspace_root`
3. `RuntimeAssembler` constructs `WorkspaceSession(workspace_root)`
4. `RuntimeBundle` exposes both `workspace_root` and `workspace_session`
5. `ToolRegistry` dispatches tool calls normally
6. tools that need workspace file access use `runtime.workspace_session`

This means workspace access becomes shared runtime infrastructure instead of ad hoc behavior embedded in each tool.

## Why This Is Better Than Adding Sandbox Now

Adding sandbox only for `code_tool` would create two write paths immediately:

- `plan_tool` writes directly to the workspace
- `code_tool` writes through sandbox

That would create inconsistent semantics for permissions, path validation, error handling, and future refactors.

By first creating a shared workspace file access layer:

- all file-mutating tools can converge on one path
- current architecture remains stable
- sandbox can later be introduced underneath the same interface

## Future Evolution to Sandbox

This design intentionally leaves a narrow seam for future sandboxing.

Phase 2 can replace or wrap the internals of `WorkspaceSession` with a sandbox-backed implementation while preserving the tool-facing interface.

Desired future migration shape:

- Phase 1: `WorkspaceSession` talks directly to the real workspace root
- Phase 2: `WorkspaceSession` delegates to a sandbox-backed access layer
- tools remain unchanged or nearly unchanged

That is the main architectural reason to add `workspace_session` now.

## Implementation Phases

### Phase 1: Establish workspace file access capability

- add `WorkspaceSession`
- inject it into `RuntimeBundle`
- update generic tool invocation so tools can access runtime when needed
- implement minimal file operations
- connect `code_tool` to `workspace_session`

### Phase 2: Migrate additional file-writing tools

- move `plan_tool` file persistence to `workspace_session`
- identify any other direct filesystem writes and converge them

### Phase 3: Add command tools separately

- add `bash_tool` or equivalent
- reuse `workspace_root` as execution cwd
- keep command execution separate from file IO abstractions

### Phase 4: Optional sandbox adoption

- add a sandbox-backed implementation behind the same runtime capability
- preserve the tool-facing contract

## Testing Strategy

Tests should cover three levels.

### Unit tests for `WorkspaceSession`

- resolves relative paths inside the workspace
- rejects path escape attempts
- reads and writes text correctly
- creates parent directories when requested
- rejects overwrite when disabled
- lists directory contents predictably
- deletes files and directories with the expected guardrails

### Runtime assembly tests

- `RuntimeAssembler` injects `workspace_session`
- injected session uses the resolved `workspace_root`

### Tool integration tests

- `code_tool` uses `runtime.workspace_session` instead of raw filesystem access
- `plan_tool` migration tests once that phase starts
- generic tool dispatch still works for tools that do not need runtime services

## Open Decisions Resolved In This Spec

- No sandbox in the first phase.
- No command execution in the workspace access layer.
- `code_tool` remains an ordinary tool.
- Shared workspace file access is a runtime capability, not a special-case tool behavior.
- Future `bash_tool` should be separate from file operations.

## Recommendation

Proceed with a minimal Phase 1 implementation centered on `WorkspaceSession`.

This gives the codebase one consistent path for file access, keeps the current structure intact, and creates the right extension point for both future tool growth and later sandboxing.
