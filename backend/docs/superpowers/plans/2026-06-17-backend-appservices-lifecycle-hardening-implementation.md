# Backend AppServices Lifecycle Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ad-hoc app wiring with `AppServices`, move lifecycle to FastAPI lifespan, and unify the runtime technical principal as `local-user` without introducing a product-level user system.

**Architecture:** Introduce a lightweight `AppServices` container that owns app-scope resources (`settings`, `redis`, `chat_run_registry`, `runtime_principal`) and exposes repository/runtime/service factories. Replace `@app.on_event(...)` with lifespan-managed startup/shutdown, route all API service construction through `app.state.services`, and inject `local-user` into runtime-facing services instead of scattering `default-user` literals.

**Tech Stack:** FastAPI, Redis asyncio client, AgentScope 2.0.1, pytest, Ruff.

---

## File Structure

- Create: `backend/app/application/services.py`
  Define `AppServices` as the app-level container for repositories, runtime adapters, service factories, and the fixed runtime principal `local-user`.
- Modify: `backend/app/main.py`
  Replace deprecated startup/shutdown hooks with lifespan and mount `app.state.services`.
- Modify: `backend/app/config.py`
  Add explicit `local_runtime_principal` setting with default `local-user`.
- Modify: `backend/app/api/sessions.py`
  Remove inline wiring helpers; resolve services through `request.app.state.services`.
- Modify: `backend/app/api/teams.py`
  Resolve services through `AppServices` instead of direct repository construction.
- Modify: `backend/app/api/workspaces.py`
  Resolve services through `AppServices` instead of direct repository construction.
- Modify: `backend/app/services/session_service.py`
  Inject runtime principal instead of hard-coded `default-user`.
- Modify: `backend/app/services/session_query_service.py`
  Inject runtime principal for runtime message history reads.
- Modify: `backend/app/services/runtime_service.py`
  Inject runtime principal and use it consistently across send/cancel/confirm/runtime sync paths.
- Modify: `backend/app/tests/test_app.py`
  Add lifespan/app-state assertions for `AppServices` and `local-user`.
- Modify: `backend/tests/test_session_api.py`
  Update runtime session assertions from `default-user` to `local-user`.
- Modify: `backend/tests/test_session_query_service.py`
  Add focused assertions for unified runtime principal use.

## Task 1: Add AppServices And Lifespan Wiring

**Files:**
- Create: `backend/app/application/services.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/tests/test_app.py`
- Test: `backend/tests/test_app.py`

- [ ] **Step 1: Write the failing lifespan/AppServices tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_app_lifespan_exposes_appservices_on_state() -> None:
    with TestClient(create_app()) as client:
        services = client.app.state.services
        assert services is not None
        assert services.runtime_principal == "local-user"
        assert services.chat_run_registry is not None


def test_app_lifespan_exposes_single_redis_client_through_appservices() -> None:
    with TestClient(create_app()) as client:
        services = client.app.state.services
        assert services.redis is not None
        assert services.session_repository()._redis is services.redis
        assert services.team_repository()._redis is services.redis
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_app.py -v`
Expected: FAIL because `app.state.services` does not exist yet and lifecycle is still managed by `@app.on_event(...)`.

- [ ] **Step 3: Write the minimal AppServices and lifespan implementation**

```python
# backend/app/application/services.py
from __future__ import annotations

from redis.asyncio import Redis

from app.config import Settings
from app.infrastructure.storage.session_repository import SessionRepository
from app.infrastructure.storage.team_repository import TeamRepository
from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.infrastructure.workspace.file_browser import WorkspaceFileBrowser
from app.infrastructure.workspace.manager import WorkspacePathManager
from app.runtime.agentscope.chat_run_registry import ChatRunRegistry
from app.runtime.agentscope.chat_runtime import AgentScopeChatRuntime
from app.runtime.agentscope.confirm_runtime import ConfirmRuntime
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime
from app.runtime.agentscope.workspace_runtime import WorkspaceRuntimeManager
from app.services.runtime_bootstrap_service import RuntimeBootstrapService
from app.services.runtime_service import RuntimeService
from app.services.session_query_service import SessionQueryService
from app.services.session_service import SessionService
from app.services.team_query_service import TeamQueryService
from app.services.team_service import TeamService
from app.services.workspace_query_service import WorkspaceQueryService
from app.services.workspace_service import WorkspaceService


class AppServices:
    def __init__(
        self,
        *,
        settings: Settings,
        redis: Redis,
        chat_run_registry: ChatRunRegistry,
    ) -> None:
        self.settings = settings
        self.redis = redis
        self.chat_run_registry = chat_run_registry
        self.runtime_principal = settings.local_runtime_principal

    def session_repository(self) -> SessionRepository:
        return SessionRepository(self.redis)

    def team_repository(self) -> TeamRepository:
        return TeamRepository(self.redis)

    def workspace_repository(self) -> WorkspaceRepository:
        return WorkspaceRepository(self.redis)

    def state_runtime(self) -> AgentScopeSessionStateRuntime:
        return AgentScopeSessionStateRuntime(redis=self.redis)

    def chat_runtime(self) -> AgentScopeChatRuntime:
        workspace_runtime = WorkspaceRuntimeManager(self.settings.workspace_base_dir)
        return AgentScopeChatRuntime(redis=self.redis, workspace_runtime=workspace_runtime)

    def confirm_runtime(self) -> ConfirmRuntime:
        return ConfirmRuntime()

    def runtime_bootstrap_service(self) -> RuntimeBootstrapService:
        return RuntimeBootstrapService(self.redis)

    def workspace_service(self) -> WorkspaceService:
        return WorkspaceService(self.workspace_repository(), WorkspacePathManager())

    def workspace_query_service(self) -> WorkspaceQueryService:
        return WorkspaceQueryService(self.workspace_repository(), WorkspaceFileBrowser())

    def team_service(self) -> TeamService:
        return TeamService(self.team_repository())

    def team_query_service(self) -> TeamQueryService:
        return TeamQueryService(self.team_repository())

    def session_service(self) -> SessionService:
        return SessionService(
            session_repository=self.session_repository(),
            team_repository=self.team_repository(),
            workspace_repository=self.workspace_repository(),
            state_runtime=self.state_runtime(),
            runtime_bootstrap_service=self.runtime_bootstrap_service(),
            runtime_principal=self.runtime_principal,
        )

    def session_query_service(self) -> SessionQueryService:
        return SessionQueryService(
            session_repository=self.session_repository(),
            team_repository=self.team_repository(),
            workspace_repository=self.workspace_repository(),
            state_runtime=self.state_runtime(),
            workspace_query_service=self.workspace_query_service(),
            runtime_principal=self.runtime_principal,
        )

    def runtime_service(self) -> RuntimeService:
        return RuntimeService(
            session_repository=self.session_repository(),
            chat_runtime=self.chat_runtime(),
            state_runtime=self.state_runtime(),
            confirm_runtime=self.confirm_runtime(),
            chat_run_registry=self.chat_run_registry,
            session_repository_factory=self.session_repository,
            chat_runtime_factory=self.chat_runtime,
            state_runtime_factory=self.state_runtime,
            runtime_principal=self.runtime_principal,
        )
```

```python
# backend/app/config.py
class Settings(BaseSettings):
    ...
    local_runtime_principal: str = "local-user"
```

```python
# backend/app/main.py
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.application.services import AppServices
from app.config import get_settings
from app.infrastructure.redis.client import get_redis_client
from app.runtime.agentscope.chat_run_registry import ChatRunRegistry


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    redis = get_redis_client()
    chat_run_registry = ChatRunRegistry()
    services = AppServices(
        settings=settings,
        redis=redis,
        chat_run_registry=chat_run_registry,
    )
    app.state.services = services
    await services.team_service().ensure_default_team()
    try:
        yield
    finally:
        await services.chat_run_registry.__aexit__()
        await services.redis.aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_app.py -v`
Expected: PASS with `app.state.services` available during `TestClient` lifespan and no functional regression in metadata/health checks.

- [ ] **Step 5: Commit**

```bash
git add app/application/services.py app/main.py app/config.py tests/test_app.py
git commit -m "refactor(backend): add app services lifecycle container"
```

## Task 2: Replace default-user With local-user Across Runtime-Facing Services

**Files:**
- Modify: `backend/app/services/session_service.py`
- Modify: `backend/app/services/session_query_service.py`
- Modify: `backend/app/services/runtime_service.py`
- Modify: `backend/tests/test_session_api.py`
- Modify: `backend/tests/test_session_query_service.py`
- Test: `backend/tests/test_session_api.py`
- Test: `backend/tests/test_session_query_service.py`

- [ ] **Step 1: Write the failing runtime principal tests**

```python
import asyncio

from fastapi.testclient import TestClient

from app.infrastructure.redis.client import get_redis_client
from app.main import create_app
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime


def test_create_session_initializes_runtime_session_with_local_user() -> None:
    with TestClient(create_app()) as client:
        workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
        team = client.post(
            "/api/v1/teams",
            json={"name": "Backend Team", "leader_agent_id": "leader-agent", "member_agent_ids": []},
        ).json()
        created = client.post(
            "/api/v1/sessions",
            json={"name": "Principal Test", "workspace_id": workspace["workspace_id"], "team_id": team["team_id"]},
        ).json()

    runtime = AgentScopeSessionStateRuntime(redis=get_redis_client())
    runtime_session = asyncio.run(
        runtime.get_runtime_session(
            "local-user",
            created["session_id"],
            created["leader_agent_id"],
        )
    )

    assert runtime_session is not None


def test_session_detail_reads_runtime_messages_with_local_user() -> None:
    with TestClient(create_app()) as client:
        workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
        team = client.post(
            "/api/v1/teams",
            json={"name": "Backend Team", "leader_agent_id": "leader-agent", "member_agent_ids": []},
        ).json()
        created = client.post(
            "/api/v1/sessions",
            json={"name": "Principal Query", "workspace_id": workspace["workspace_id"], "team_id": team["team_id"]},
        ).json()
        client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "hello local principal"},
        )
        payload = client.get(f"/api/v1/sessions/{created['session_id']}").json()

    assert any(message["role"] == "user" for message in payload["messages"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_session_api.py tests/test_session_query_service.py -v`
Expected: FAIL because runtime-facing services still use hard-coded `default-user`.

- [ ] **Step 3: Write the minimal runtime principal implementation changes**

```python
# backend/app/services/session_service.py
class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        team_repository: TeamRepository,
        workspace_repository: WorkspaceRepository,
        state_runtime: AgentScopeSessionStateRuntime,
        runtime_bootstrap_service: RuntimeBootstrapService,
        runtime_principal: str,
    ) -> None:
        ...
        self._runtime_principal = runtime_principal

    async def create_session(...):
        ...
        await self._runtime_bootstrap_service.ensure_runtime_agent(
            user_id=self._runtime_principal,
            agent_template=leader_agent,
        )
        chat_model_config = await self._runtime_bootstrap_service.build_default_chat_model_config(
            user_id=self._runtime_principal,
        )
        ...
        await self._state_runtime.create_runtime_session(
            user_id=self._runtime_principal,
            ...
        )
```

```python
# backend/app/services/session_query_service.py
class SessionQueryService:
    def __init__(
        self,
        session_repository: SessionRepository,
        team_repository: TeamRepository,
        workspace_repository: WorkspaceRepository,
        state_runtime: AgentScopeSessionStateRuntime,
        workspace_query_service: WorkspaceQueryService,
        runtime_principal: str,
    ) -> None:
        ...
        self._runtime_principal = runtime_principal

    async def get_session_detail(self, session_id: str) -> dict:
        ...
        messages = await self._state_runtime.list_runtime_messages(
            user_id=self._runtime_principal,
            session_id=session.session_id,
        )
```

```python
# backend/app/services/runtime_service.py
class RuntimeService:
    def __init__(
        self,
        session_repository: SessionRepository,
        chat_runtime: AgentScopeChatRuntime | None = None,
        state_runtime: AgentScopeSessionStateRuntime | None = None,
        confirm_runtime: ConfirmRuntime | None = None,
        chat_run_registry=None,
        session_repository_factory: Callable[[], SessionRepository] | None = None,
        chat_runtime_factory: Callable[[], AgentScopeChatRuntime] | None = None,
        state_runtime_factory: Callable[[], AgentScopeSessionStateRuntime] | None = None,
        runtime_principal: str = "local-user",
    ) -> None:
        ...
        self._runtime_principal = runtime_principal

    async def send_message(self, session_id: str, content: str) -> None:
        ...
        async def _run_and_sync() -> None:
            ...
            await chat_runtime.run_user_message(
                user_id=self._runtime_principal,
                ...
            )
            ...

    async def submit_waiting_item(...):
        runtime_session = await self._state_runtime.get_runtime_session(
            user_id=self._runtime_principal,
            ...
        )
        ...
        await self._chat_runtime.continue_with_confirm_event(
            user_id=self._runtime_principal,
            ...
        )

    async def _sync_runtime_state(...):
        runtime_session = await state_runtime.get_runtime_session(
            user_id=self._runtime_principal,
            ...
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_session_api.py tests/test_session_query_service.py -v`
Expected: PASS with all runtime session create/read/send/query paths using `local-user`.

- [ ] **Step 5: Commit**

```bash
git add app/services/session_service.py app/services/session_query_service.py app/services/runtime_service.py tests/test_session_api.py tests/test_session_query_service.py
git commit -m "refactor(backend): unify local runtime principal"
```

## Task 3: Route API Wiring Through AppServices

**Files:**
- Modify: `backend/app/api/sessions.py`
- Modify: `backend/app/api/teams.py`
- Modify: `backend/app/api/workspaces.py`
- Modify: `backend/tests/test_app.py`
- Modify: `backend/tests/test_team_api.py`
- Modify: `backend/tests/test_workspace_api.py`
- Test: `backend/tests/test_app.py`
- Test: `backend/tests/test_team_api.py`
- Test: `backend/tests/test_workspace_api.py`

- [ ] **Step 1: Write the failing router wiring tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_team_routes_use_appservices_container() -> None:
    with TestClient(create_app()) as client:
        assert client.app.state.services is not None
        response = client.get("/api/v1/teams")
    assert response.status_code == 200


def test_workspace_routes_use_appservices_container() -> None:
    with TestClient(create_app()) as client:
        assert client.app.state.services is not None
        response = client.post("/api/v1/workspaces", json={"name": "Project Alpha"})
    assert response.status_code == 201
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_app.py tests/test_team_api.py tests/test_workspace_api.py -v`
Expected: FAIL if routes still rely on local helper constructors instead of `app.state.services`.

- [ ] **Step 3: Write the minimal router wiring changes**

```python
# backend/app/api/teams.py
from fastapi import APIRouter, Request

...


@team_router.get("")
async def list_teams(request: Request) -> dict:
    services = request.app.state.services
    writer = services.team_service()
    await writer.ensure_default_team()
    service = services.team_query_service()
    return await service.list_teams()


@team_router.post("", status_code=201)
async def create_team(body: CreateTeamRequest, request: Request) -> dict:
    service = request.app.state.services.team_service()
    record = await service.create_team(...)
    return record.model_dump(mode="json")
```

```python
# backend/app/api/workspaces.py
from fastapi import APIRouter, HTTPException, Query, Request

...


@workspace_router.post("", status_code=201)
async def create_workspace(body: CreateWorkspaceRequest, request: Request) -> dict:
    service = request.app.state.services.workspace_service()
    record = await service.create_workspace(body.name, body.description)
    return record.model_dump(mode="json")


@workspace_router.get("")
async def list_workspaces(request: Request) -> dict:
    service = request.app.state.services.workspace_query_service()
    return await service.list_workspaces()
```

```python
# backend/app/api/sessions.py
from fastapi import APIRouter, HTTPException, Request

...


@session_router.post("", status_code=201)
async def create_session(body: CreateSessionRequest, request: Request) -> dict:
    service = request.app.state.services.session_service()
    ...


@session_router.get("")
async def list_sessions(request: Request) -> dict:
    return await request.app.state.services.session_query_service().list_sessions()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_app.py tests/test_team_api.py tests/test_workspace_api.py -v`
Expected: PASS with router-level wiring fully resolved through `AppServices`.

- [ ] **Step 5: Commit**

```bash
git add app/api/sessions.py app/api/teams.py app/api/workspaces.py tests/test_app.py tests/test_team_api.py tests/test_workspace_api.py
git commit -m "refactor(backend): route api wiring through app services"
```

## Task 4: Run Full Verification For Hardening Changes

**Files:**
- Modify: `backend/app/application/services.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/api/sessions.py`
- Modify: `backend/app/api/teams.py`
- Modify: `backend/app/api/workspaces.py`
- Modify: `backend/app/services/session_service.py`
- Modify: `backend/app/services/session_query_service.py`
- Modify: `backend/app/services/runtime_service.py`
- Modify: `backend/tests/test_app.py`
- Modify: `backend/tests/test_session_api.py`
- Modify: `backend/tests/test_session_query_service.py`
- Modify: `backend/tests/test_team_api.py`
- Modify: `backend/tests/test_workspace_api.py`

- [ ] **Step 1: Run focused hardening test suite**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_app.py tests/test_session_api.py tests/test_session_query_service.py tests/test_team_api.py tests/test_workspace_api.py -v`
Expected: PASS, confirming lifespan, `AppServices`, `local-user`, and router wiring are stable.

- [ ] **Step 2: Run runtime regression suite**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_runtime_service.py tests/test_session_stream.py -v`
Expected: PASS, confirming the previous async runtime mainline work did not regress.

- [ ] **Step 3: Run Ruff on all app and test files**

Run: `& ".\.venv\Scripts\python.exe" -m ruff check app tests`
Expected: PASS with no new lint violations.

- [ ] **Step 4: Commit**

```bash
git add app application services tests
git commit -m "refactor(backend): harden app services lifecycle"
```
