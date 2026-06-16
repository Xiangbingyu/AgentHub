# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AgentHub is a multi-agent engineering-collaboration platform. A user talks to one or more专业 Agents; an **Orchestrator** agent breaks goals into a dynamic Plan, delegates subtasks to **Worker** agents, collects callbacks, and updates the Plan. Code changes are meant to land in isolated workspaces as Proposals before merging. See `backend-python/docs/方案/AgentHub总体方案设计.md` for the full product design and `backend-python/docs/superpowers/specs/` + `plans/` for per-feature designs.

The repo has three parts:
- `backend-python/` — Python (uv + FastAPI), the core. Two services: `agent_service` (the agent runtime) and `gateway_service` (a thin HTTP/SSE gateway in front of it).
- `frontend/` — React 19 + Vite SPA (currently a scaffold).
- `docs/`, `.trae/skills/` — design docs and skill definitions.

## Commands

All backend commands run from `backend-python/` (tests rely on `pythonpath = ["."]` set there).

```bash
cd backend-python
uv sync                                          # install deps (manages Python 3.11 automatically)
uv run pytest                                    # run all tests (agent_service/tests + gateway_service/tests)
uv run pytest agent_service/tests/test_delegate_tool.py            # single test file
uv run pytest agent_service/tests/test_delegate_tool.py::test_name # single test
uv run ruff check .                              # lint (line-length 100, rules E/F/I)

uv run fastapi dev agent_service/app/main.py     # run agent_service (default :8000)
uv run fastapi dev gateway_service/app/main.py   # run gateway_service
```

Note: `backend-python/README.md` is stale — it references an old top-level `app/main.py` layout that has since been split into `agent_service/` and `gateway_service/`. Use the paths above.

Frontend:
```bash
cd frontend
npm install
npm run dev      # vite dev server
npm run build
npm run lint     # eslint
```

## Environment

`agent_service` needs an OpenAI-compatible LLM endpoint. `InternalLlmExecutor` (`agent_service/app/llm/llm_executor.py`) raises at construction unless these are set (copy `backend-python/.env.example` to `.env`):
- `TEST_API_KEY`, `TEST_BASE_URL`, `TEST_MODEL` — LLM provider config (also used by e2e tests; tests that hit a real LLM skip when unset).
- `SQLITE_DB_PATH` — defaults to `./.AgentHub/agenthub.db`.

`gateway_service` reads `AGENT_SERVICE_BASE_URL` (defaults to `http://localhost:8000`).

## Architecture

### Request → run → loop

`agent_service` exposes runs over HTTP (`agent_service/app/api/`). The central flow lives in `services/agent_run_input_service.py` (`AgentRunInputService.input`):

1. **Idempotency**: input events are deduped by `idempotency_key` per run.
2. **RuntimeAssembler.build(run_id)** (`runtime/runtime_assembler.py`) loads the run + agent and assembles a `RuntimeBundle` — the single context object threaded through everything. It resolves, via dedicated resolver classes under `runtime/`: workspace root, role, executor/prompt/tool **config**, skills, MCP runtime, the **ToolRegistry**, an instruction view, and a tool view.
3. **PromptComposer.compose** (`runtime/prompt/prompt_composer.py`) builds system + context prompts from ordered sections (provider, environment, instruction, project instructions, skills, role, tools, optional user prompt).
4. The executor calls the LLM. Tool calls are dispatched through `ToolRegistry.dispatch`, and for orchestrators a bounded tool loop (`_run_internal_orchestrator_tool_loop`, max 8 rounds) feeds tool results back as messages.
5. **LoopEngine** (`runtime/loop_engine.py`) is a status state machine keyed on `(role, status, input_event.type)`. It decides continue / wait / stop and advances run status (e.g. orchestrator `created`→`chatting`; `updating_plan`→`completed`/`failed` on worker callback).

### Orchestrator / Worker delegation

`role` is `"orchestrator"` or `"worker"`. Orchestrators get `plan_tool`, `delegate_tool`, and `bash_tool`. `DelegateTool` (`tools/delegate_tool.py`) is the heart of multi-agent flow:
- Creates a child worker `AgentRunModel` + a `SubtaskModel`, sets the parent run to `waiting_callback`.
- Runs the worker **in a background thread** (`_run_async`) by re-entering `AgentRunInputService.input` with a `user_input` event.
- On worker completion, re-enters the parent run with a `worker_callback` event carrying the result; the parent's LoopEngine transition produces `completed`/`failed`.

Runs form a tree: `parent_run_id` / `root_run_id` link delegated runs.

### Tools

Tools have two-part definitions: a **schema builder + request model** in `schemas/` (the LLM-facing JSON definition and Pydantic validation) and an **implementation** in `tools/`. `ToolResolver` (`runtime/tools/tool_resolver.py`) maps configured tool names to registered `ToolSpec`s — note `plan_tool` also pulls in `delegate_tool` + `bash_tool`, and `code_tool` pulls in `bash_tool`. Coding tools include `code_tool`, `bash_tool`, and external-framework adapters `claude_code_tool` / `opencode_tool` (`tools/framework_adapters/`). MCP tools are merged in from the resolved MCP runtime.

### Persistence

SQLite, one table per aggregate, each row storing a Pydantic model serialized as JSON in a `payload` column (see `database/schema.py`). Repositories (`repositories/*.py`) open a connection per call, `INSERT OR REPLACE` the JSON, and validate it back on read. Models live in `models/`. `database/bootstrap.py` initializes the schema and seeds default agents on app startup; there is also an in-memory `STORE` (`database/memory_store.py`) used for seeding/tests.

### Config snapshots

An agent's behavior comes from its config blocks (`prompt_policy`, `tool_config`, `skill_config`, `mcp_config`, `executor_config`). `RuntimeSnapshotResolver` freezes these onto a run's `runtime_snapshot` so a run is reproducible even if the agent config later changes; delegated worker runs get a default snapshot built from the worker agent.

### Gateway

`gateway_service` is intentionally thin: page endpoints (`api/session_page.py`, `workspace_page.py`) and an SSE `api/session_stream.py` that streams session domain events. It talks to `agent_service` via `client/agent_service_client.py` (currently a stub returning empty lists — wire-up is in progress).

## Conventions

- Imports are absolute from the service package root, e.g. `from agent_service.app.runtime... import ...`. Match this.
- Models are Pydantic; pass changes via `model_copy(update={...})` rather than mutating in place (the repository pattern relies on full-document writes).
- Reply in the user's language. Much of the design documentation and many docstrings are in Chinese.
- Two skills are defined under `.trae/skills/`: `karpathy-guidelines` (simplicity / surgical-change discipline) and `enterprise-react-frontend` (frontend conventions). Consult them when relevant.
