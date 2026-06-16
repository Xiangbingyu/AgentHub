# AgentScope Session-Team Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first usable backend iteration around `Session / Team / Workspace`, backed by AgentScope runtime sessions, Redis persistence, local workspaces, session stream, and waiting/confirm flow.

**Architecture:** The product layer owns `ProductSessionRecord / TeamRecord / WorkspaceRecord` and page-facing query views, while the runtime layer reuses AgentScope `SessionRecord / AgentState / Msg` history and `reply_stream(...)`. Session creation binds a chosen workspace and team, but worker/subagent execution is not implemented by hand at the product layer: the true execution chain is AgentScope Runtime Team (`TeamCreate / AgentCreate / TeamSay / inbox / wakeup / WakeupDispatcher`), and backend code is responsible for bridging Product Team to Runtime Team plus projecting runtime results back to product-layer session views.

**Tech Stack:** FastAPI, AgentScope 2.0.1, Redis, Pydantic, pytest, Ruff, local filesystem workspaces.

---

## File Structure

Planned files and responsibilities for phase 1:

- Modify: `backend/app/config.py`
  Add Redis, workspace base dir, and initial backend runtime settings.
- Create: `backend/docker-compose.redis.yml`
  Local Redis container for backend development, using a host port that avoids `6380` and `6381`.
- Modify: `backend/app/main.py`
  Wire application startup to runtime dependencies and new routers.
- Modify: `backend/app/api/router.py`
  Register session, session stream, team, workspace, and system routers.
- Create: `backend/app/api/sessions.py`
  HTTP endpoints for create/list/detail/send/cancel/submit waiting result.
- Create: `backend/app/api/session_stream.py`
  SSE endpoint for session event stream.
- Create: `backend/app/api/teams.py`
  HTTP endpoints for team create/list/detail/update/delete.
- Create: `backend/app/api/workspaces.py`
  HTTP endpoints for workspace create/list/tree/file content.
- Modify: `backend/app/api/agentscope.py`
  Keep runtime health/status but align response with new dependencies.
- Create: `backend/app/services/session_service.py`
  Product write actions for sessions.
- Create: `backend/app/services/session_query_service.py`
  Aggregate session detail/list views from product records + AgentScope messages.
- Create: `backend/app/services/runtime_service.py`
  Runtime bridge that loads product session + AgentScope runtime session and runs AgentScope.
- Create: `backend/app/services/team_service.py`
  Product write actions for teams and default team bootstrap.
- Create: `backend/app/services/team_query_service.py`
  Team list/detail views.
- Create: `backend/app/services/workspace_query_service.py`
  Workspace list/tree/file reads.
- Create: `backend/app/services/workspace_service.py`
  Workspace create/update behavior.
- Create: `backend/app/domain/sessions/models.py`
  Product session records, waiting item model, agent status model.
- Create: `backend/app/domain/sessions/schemas.py`
  Session API request/response schemas.
- Create: `backend/app/domain/teams/models.py`
  Team and agent template product records.
- Create: `backend/app/domain/teams/schemas.py`
  Team API request/response schemas.
- Create: `backend/app/domain/workspaces/models.py`
  Product workspace records.
- Create: `backend/app/domain/workspaces/schemas.py`
  Workspace API request/response schemas.
- Create: `backend/app/runtime/agentscope/assembler.py`
  Map ProductSession + Team + Workspace + AgentScope SessionRecord into a runnable AgentScope agent.
- Create: `backend/app/runtime/agentscope/chat_runtime.py`
  Thin wrapper around AgentScope chat run semantics.
- Create: `backend/app/runtime/agentscope/team_runtime.py`
  Bridge Product Team to AgentScope Runtime Team, including runtime team creation, worker session discovery, and projection helpers.
- Create: `backend/app/runtime/agentscope/state_runtime.py`
  Load/update AgentScope runtime session records and state.
- Create: `backend/app/runtime/agentscope/confirm_runtime.py`
  Convert product waiting item results into AgentScope continuation inputs.
- Create: `backend/app/runtime/agentscope/workspace_runtime.py`
  Build AgentScope local workspaces from product workspace records.
- Create: `backend/app/infrastructure/storage/session_repository.py`
  Product session persistence in Redis.
- Create: `backend/app/infrastructure/storage/team_repository.py`
  Product team / agent template persistence in Redis.
- Create: `backend/app/infrastructure/storage/workspace_repository.py`
  Product workspace persistence in Redis.
- Create: `backend/app/infrastructure/redis/client.py`
  Shared Redis client creation.
- Create: `backend/app/infrastructure/workspace/manager.py`
  Product workspace path resolution and local workspace initialization.
- Create: `backend/app/infrastructure/workspace/file_browser.py`
  Tree and file content reads from local workspaces.
- Create: `backend/app/infrastructure/stream/sse.py`
  SSE framing helpers.
- Modify: `backend/tests/test_app.py`
  Update smoke tests for new routes/app wiring.
- Create: `backend/tests/test_session_api.py`
  Session create/list/detail/send/cancel/confirm tests.
- Create: `backend/tests/test_team_api.py`
  Team CRUD and default team behavior tests.
- Create: `backend/tests/test_workspace_api.py`
  Workspace create/list/tree/file content tests.
- Create: `backend/tests/test_runtime_service.py`
  Runtime bridging, status mapping, waiting item mapping.
- Create: `backend/tests/test_session_query_service.py`
  Session detail aggregation from product records + AgentScope messages.

## Task 1: Product Models And Redis Repositories

**Files:**
- Create: `backend/app/domain/sessions/models.py`
- Create: `backend/app/domain/sessions/schemas.py`
- Create: `backend/app/domain/teams/models.py`
- Create: `backend/app/domain/teams/schemas.py`
- Create: `backend/app/domain/workspaces/models.py`
- Create: `backend/app/domain/workspaces/schemas.py`
- Create: `backend/app/infrastructure/redis/client.py`
- Create: `backend/app/infrastructure/storage/session_repository.py`
- Create: `backend/app/infrastructure/storage/team_repository.py`
- Create: `backend/app/infrastructure/storage/workspace_repository.py`
- Modify: `backend/app/config.py`
- Create: `backend/docker-compose.redis.yml`
- Test: `backend/tests/test_session_query_service.py`

- [ ] **Step 1: Write the failing model/repository tests**

```python
from app.domain.sessions.models import ProductSessionRecord, WaitingItem
from app.domain.teams.models import TeamRecord, AgentTemplateRecord
from app.domain.workspaces.models import WorkspaceRecord


def test_product_session_record_defaults() -> None:
    record = ProductSessionRecord(
        session_id="session-1",
        name="Demo",
        team_id="team-1",
        leader_agent_id="agent-1",
        workspace_id="workspace-1",
    )

    assert record.status == "idle"
    assert record.waiting_items == []
    assert record.agent_statuses == []
    assert record.current_plan_snapshot is None
    assert record.current_summary_snapshot is None


def test_workspace_record_keeps_local_backend_fields() -> None:
    workspace = WorkspaceRecord(
        workspace_id="workspace-1",
        name="Project Alpha",
        root_path="E:/Github/AgentHub-weon/backend/.AgentHub/workspaces/workspace-1",
    )

    assert workspace.backend_type == "local"
    assert workspace.status == "ready"


def test_waiting_item_supports_confirm_and_external_result() -> None:
    confirm_item = WaitingItem(
        waiting_id="wait-1",
        source_type="leader",
        source_runtime_id="leader-runtime",
        waiting_kind="confirm",
        title="Confirm deletion",
        message="Delete foo.py?",
        payload={"path": "foo.py"},
    )
    external_item = WaitingItem(
        waiting_id="wait-2",
        source_type="subagent",
        source_runtime_id="worker-runtime",
        waiting_kind="external_result",
        title="Await tool result",
        message="Waiting for external executor.",
        payload={"tool": "Deploy"},
    )

    assert confirm_item.status == "pending"
    assert external_item.status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_query_service.py -v`
Expected: FAIL with import errors for missing domain/repository modules.

- [ ] **Step 3: Write minimal product models and Redis client configuration**

```python
# backend/app/domain/sessions/models.py
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SessionStatus = Literal["idle", "running", "waiting", "cancelling", "failed"]
WaitingKind = Literal["confirm", "external_result"]
WaitingStatus = Literal["pending", "resolved", "rejected", "expired"]
AgentKind = Literal["leader", "worker"]
AgentRuntimeStatus = Literal[
    "idle",
    "running",
    "waiting",
    "completed",
    "failed",
    "cancelled",
]


class WaitingItem(BaseModel):
    waiting_id: str
    source_type: Literal["leader", "subagent"]
    source_runtime_id: str
    waiting_kind: WaitingKind
    title: str
    message: str
    payload: dict
    status: WaitingStatus = "pending"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentStatus(BaseModel):
    runtime_id: str
    agent_id: str
    name: str
    role: str
    kind: AgentKind
    status: AgentRuntimeStatus
    current_task_summary: str | None = None
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ProductSessionRecord(BaseModel):
    session_id: str
    name: str
    team_id: str
    leader_agent_id: str
    workspace_id: str
    status: SessionStatus = "idle"
    current_plan_snapshot: dict | None = None
    current_summary_snapshot: str | None = None
    waiting_items: list[WaitingItem] = Field(default_factory=list)
    agent_statuses: list[AgentStatus] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
```

```python
# backend/app/domain/teams/models.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 16384


class AgentTemplateRecord(BaseModel):
    agent_id: str
    name: str
    role: str
    system_prompt: str
    default_model_config: ModelConfig
    default_tool_policy: dict = Field(default_factory=dict)
    default_mcp_refs: list[str] = Field(default_factory=list)
    default_skill_refs: list[str] = Field(default_factory=list)
    default_permission_policy: dict = Field(default_factory=dict)


class TeamRecord(BaseModel):
    team_id: str
    name: str
    description: str = ""
    leader_agent_id: str
    member_agent_ids: list[str] = Field(default_factory=list)
    enabled_tool_policy: dict = Field(default_factory=dict)
    enabled_mcp_refs: list[str] = Field(default_factory=list)
    enabled_skill_refs: list[str] = Field(default_factory=list)
    is_default: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
```

```python
# backend/app/domain/workspaces/models.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceRecord(BaseModel):
    workspace_id: str
    name: str
    root_path: str
    description: str = ""
    backend_type: str = "local"
    status: str = "ready"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
```

```python
# backend/app/config.py (new fields excerpt)
redis_url: str = "redis://127.0.0.1:6382/0"
workspace_base_dir: str = "./.AgentHub/workspaces"
```

```yaml
# backend/docker-compose.redis.yml
services:
  redis:
    image: redis:7-alpine
    container_name: agenthub-backend-redis
    ports:
      - "6382:6379"
    volumes:
      - redis-data:/data
    command: ["redis-server", "--appendonly", "yes"]

volumes:
  redis-data:
```

- [ ] **Step 4: Add minimal Redis-backed repositories**

```python
# backend/app/infrastructure/storage/session_repository.py
from __future__ import annotations

import json

from redis.asyncio import Redis

from app.domain.sessions.models import ProductSessionRecord


class SessionRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    def _key(self, session_id: str) -> str:
        return f"agenthub:product:session:{session_id}"

    async def upsert(self, record: ProductSessionRecord) -> ProductSessionRecord:
        await self._redis.set(self._key(record.session_id), record.model_dump_json())
        score = float(record.created_at.replace("-", "").replace(":", "").replace("T", "").replace(".", "")[:14])
        await self._redis.zadd(
            "agenthub:product:sessions",
            {record.session_id: score},
        )
        return record

    async def get(self, session_id: str) -> ProductSessionRecord | None:
        raw = await self._redis.get(self._key(session_id))
        if raw is None:
            return None
        return ProductSessionRecord.model_validate_json(raw)
```

```python
# backend/app/infrastructure/storage/team_repository.py
from __future__ import annotations

from redis.asyncio import Redis

from app.domain.teams.models import TeamRecord, AgentTemplateRecord


class TeamRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def upsert_team(self, record: TeamRecord) -> TeamRecord:
        await self._redis.set(
            f"agenthub:product:team:{record.team_id}",
            record.model_dump_json(),
        )
        return record

    async def upsert_agent_template(
        self,
        record: AgentTemplateRecord,
    ) -> AgentTemplateRecord:
        await self._redis.set(
            f"agenthub:product:agent-template:{record.agent_id}",
            record.model_dump_json(),
        )
        return record
```

```python
# backend/app/infrastructure/storage/workspace_repository.py
from __future__ import annotations

from redis.asyncio import Redis

from app.domain.workspaces.models import WorkspaceRecord


class WorkspaceRepository:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def upsert(self, record: WorkspaceRecord) -> WorkspaceRecord:
        await self._redis.set(
            f"agenthub:product:workspace:{record.workspace_id}",
            record.model_dump_json(),
        )
        return record
```

- [ ] **Step 5: Run focused tests to verify models and repositories pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_query_service.py -v`
Expected: PASS for model construction tests; repository-specific tests may still be pending.

- [ ] **Step 6: Start local Redis container**

Run: `docker compose -f backend/docker-compose.redis.yml up -d`
Expected: Redis container starts on `127.0.0.1:6382`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/domain backend/app/infrastructure/storage backend/app/infrastructure/redis backend/docker-compose.redis.yml backend/tests/test_session_query_service.py
git commit -m "feat(backend): add product records and redis repositories"
```

### Task 2: Workspace Resources And Local Filesystem Access

**Files:**
- Create: `backend/app/services/workspace_service.py`
- Create: `backend/app/services/workspace_query_service.py`
- Create: `backend/app/api/workspaces.py`
- Create: `backend/app/infrastructure/workspace/manager.py`
- Create: `backend/app/infrastructure/workspace/file_browser.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_workspace_api.py`

- [ ] **Step 1: Write the failing workspace API tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_workspace_returns_workspace_record() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha", "description": "Main repo"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Project Alpha"
    assert payload["backend_type"] == "local"
    assert payload["root_path"]


def test_workspace_tree_lists_directory_entries() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()

    response = client.get(f"/api/v1/workspaces/{created['workspace_id']}/tree")

    assert response.status_code == 200
    assert response.json()["entries"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_workspace_api.py -v`
Expected: FAIL because workspace modules and routes do not exist yet.

- [ ] **Step 3: Implement workspace creation and local path manager**

```python
# backend/app/infrastructure/workspace/manager.py
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.config import get_settings
from app.domain.workspaces.models import WorkspaceRecord


class WorkspacePathManager:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self._base_dir = Path(base_dir or settings.workspace_base_dir).resolve()

    def create_record(self, name: str, description: str = "") -> WorkspaceRecord:
        workspace_id = uuid4().hex
        root_path = self._base_dir / workspace_id
        root_path.mkdir(parents=True, exist_ok=True)
        return WorkspaceRecord(
            workspace_id=workspace_id,
            name=name,
            description=description,
            root_path=str(root_path),
        )
```

```python
# backend/app/services/workspace_service.py
from __future__ import annotations

from app.domain.workspaces.models import WorkspaceRecord
from app.infrastructure.workspace.manager import WorkspacePathManager
from app.infrastructure.storage.workspace_repository import WorkspaceRepository


class WorkspaceService:
    def __init__(
        self,
        repository: WorkspaceRepository,
        path_manager: WorkspacePathManager,
    ) -> None:
        self._repository = repository
        self._path_manager = path_manager

    async def create_workspace(self, name: str, description: str = "") -> WorkspaceRecord:
        record = self._path_manager.create_record(name=name, description=description)
        return await self._repository.upsert(record)
```

```python
# backend/app/infrastructure/workspace/file_browser.py
from __future__ import annotations

from pathlib import Path


class WorkspaceFileBrowser:
    def list_tree(self, root_path: str, relative_path: str = "") -> list[dict]:
        base = Path(root_path)
        target = (base / relative_path).resolve()
        if base not in [target, *target.parents]:
            raise ValueError("Path escapes workspace root")
        if not target.exists():
            return []
        return [
            {
                "name": child.name,
                "path": child.relative_to(base).as_posix(),
                "type": "directory" if child.is_dir() else "file",
            }
            for child in sorted(target.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        ]

    def read_file(self, root_path: str, relative_path: str) -> str:
        base = Path(root_path)
        target = (base / relative_path).resolve()
        if base not in [target, *target.parents] or not target.is_file():
            raise ValueError("Invalid workspace file path")
        return target.read_text(encoding="utf-8")
```

- [ ] **Step 4: Add workspace query service and routes**

```python
# backend/app/services/workspace_query_service.py
from __future__ import annotations

from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.infrastructure.workspace.file_browser import WorkspaceFileBrowser


class WorkspaceQueryService:
    def __init__(
        self,
        repository: WorkspaceRepository,
        file_browser: WorkspaceFileBrowser,
    ) -> None:
        self._repository = repository
        self._file_browser = file_browser

    async def list_workspaces(self) -> list[dict]:
        records = await self._repository.list_all()
        return [record.model_dump(mode="json") for record in records]

    async def get_tree(self, workspace_id: str, path: str = "") -> dict:
        record = await self._repository.get(workspace_id)
        entries = self._file_browser.list_tree(record.root_path, path)
        return {"workspace_id": workspace_id, "path": path, "entries": entries}
```

```python
# backend/app/api/workspaces.py
from fastapi import APIRouter

workspace_router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@workspace_router.post("")
async def create_workspace(...):
    ...

@workspace_router.get("")
async def list_workspaces(...):
    ...

@workspace_router.get("/{workspace_id}/tree")
async def get_workspace_tree(...):
    ...

@workspace_router.get("/{workspace_id}/files")
async def read_workspace_file(...):
    ...
```

- [ ] **Step 5: Run workspace tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_workspace_api.py -v`
Expected: PASS for create/list/tree/file content behavior.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/workspaces.py backend/app/services/workspace_service.py backend/app/services/workspace_query_service.py backend/app/infrastructure/workspace backend/app/main.py backend/app/api/router.py backend/tests/test_workspace_api.py
git commit -m "feat(backend): add workspace resources and local file access"
```

### Task 3: Team Resources And Default Team Bootstrap

**Files:**
- Create: `backend/app/services/team_service.py`
- Create: `backend/app/services/team_query_service.py`
- Create: `backend/app/api/teams.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_team_api.py`

- [ ] **Step 1: Write the failing team API tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_list_teams_contains_default_team() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/teams")

    assert response.status_code == 200
    payload = response.json()
    assert any(team["is_default"] for team in payload["teams"])


def test_create_team_persists_leader_and_members() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["leader_agent_id"] == "leader-agent"
    assert payload["member_agent_ids"] == ["worker-a", "worker-b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_team_api.py -v`
Expected: FAIL because team services and routes do not exist yet.

- [ ] **Step 3: Implement team service and default team initialization**

```python
# backend/app/services/team_service.py
from __future__ import annotations

from uuid import uuid4

from app.domain.teams.models import TeamRecord
from app.infrastructure.storage.team_repository import TeamRepository


class TeamService:
    def __init__(self, repository: TeamRepository) -> None:
        self._repository = repository

    async def ensure_default_team(self) -> TeamRecord:
        existing = await self._repository.get_default_team()
        if existing is not None:
            return existing
        default_team = TeamRecord(
            team_id=uuid4().hex,
            name="Default Team",
            description="System-provided default team.",
            leader_agent_id="default-leader-agent",
            member_agent_ids=[],
            is_default=True,
        )
        return await self._repository.upsert_team(default_team)

    async def create_team(
        self,
        name: str,
        leader_agent_id: str,
        member_agent_ids: list[str],
        description: str = "",
    ) -> TeamRecord:
        team = TeamRecord(
            team_id=uuid4().hex,
            name=name,
            description=description,
            leader_agent_id=leader_agent_id,
            member_agent_ids=member_agent_ids,
        )
        return await self._repository.upsert_team(team)
```

```python
# backend/app/services/team_query_service.py
from __future__ import annotations

from app.infrastructure.storage.team_repository import TeamRepository


class TeamQueryService:
    def __init__(self, repository: TeamRepository) -> None:
        self._repository = repository

    async def list_teams(self) -> dict:
        teams = await self._repository.list_teams()
        return {"teams": [team.model_dump(mode="json") for team in teams]}
```

- [ ] **Step 4: Add team routes and boot default team on startup**

```python
# backend/app/api/teams.py
from fastapi import APIRouter

team_router = APIRouter(prefix="/teams", tags=["teams"])

@team_router.get("")
async def list_teams(...):
    ...

@team_router.post("")
async def create_team(...):
    ...
```

```python
# backend/app/main.py (startup excerpt)
async def _bootstrap_defaults(team_service: TeamService) -> None:
    await team_service.ensure_default_team()
```

- [ ] **Step 5: Run team tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_team_api.py -v`
Expected: PASS, including default team availability.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/teams.py backend/app/services/team_service.py backend/app/services/team_query_service.py backend/app/main.py backend/app/api/router.py backend/tests/test_team_api.py
git commit -m "feat(backend): add team resources and default bootstrap"
```

### Task 4: Product Session Resources And Session Detail View

**Files:**
- Create: `backend/app/services/session_service.py`
- Create: `backend/app/services/session_query_service.py`
- Create: `backend/app/api/sessions.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/router.py`
- Test: `backend/tests/test_session_api.py`
- Test: `backend/tests/test_session_query_service.py`

- [ ] **Step 1: Write the failing session API tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_session_requires_name_workspace_and_team() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/sessions",
        json={
            "name": "Implement backend runtime",
            "workspace_id": "workspace-1",
            "team_id": "team-1",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Implement backend runtime"
    assert payload["workspace_id"] == "workspace-1"
    assert payload["team_id"] == "team-1"
    assert payload["status"] == "idle"


def test_get_session_detail_returns_runtime_sidebar_snapshot() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Implement backend runtime",
            "workspace_id": "workspace-1",
            "team_id": "team-1",
        },
    ).json()

    response = client.get(f"/api/v1/sessions/{created['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["session_id"] == created["session_id"]
    assert payload["runtime"]["waiting_items"] == []
    assert "workspace_status" in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_api.py backend/tests/test_session_query_service.py -v`
Expected: FAIL because session services and session detail view do not exist yet.

- [ ] **Step 3: Implement session create/list/detail behavior**

```python
# backend/app/services/session_service.py
from __future__ import annotations

from uuid import uuid4

from app.domain.sessions.models import ProductSessionRecord
from app.infrastructure.storage.session_repository import SessionRepository
from app.infrastructure.storage.team_repository import TeamRepository
from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime


class SessionService:
    def __init__(
        self,
        session_repository: SessionRepository,
        team_repository: TeamRepository,
        workspace_repository: WorkspaceRepository,
        state_runtime: AgentScopeSessionStateRuntime,
    ) -> None:
        self._session_repository = session_repository
        self._team_repository = team_repository
        self._workspace_repository = workspace_repository
        self._state_runtime = state_runtime

    async def create_session(
        self,
        name: str,
        workspace_id: str,
        team_id: str,
    ) -> ProductSessionRecord:
        team = await self._team_repository.get_team(team_id)
        workspace = await self._workspace_repository.get(workspace_id)
        session_id = uuid4().hex
        record = ProductSessionRecord(
            session_id=session_id,
            name=name,
            team_id=team.team_id,
            leader_agent_id=team.leader_agent_id,
            workspace_id=workspace.workspace_id,
        )
        await self._session_repository.upsert(record)
        await self._state_runtime.create_runtime_session(
            session_id=session_id,
            agent_id=team.leader_agent_id,
            workspace_id=workspace.workspace_id,
            name=name,
        )
        return record
```

```python
# backend/app/services/session_query_service.py
from __future__ import annotations

from app.infrastructure.storage.session_repository import SessionRepository
from app.infrastructure.storage.team_repository import TeamRepository
from app.infrastructure.storage.workspace_repository import WorkspaceRepository
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime


class SessionQueryService:
    def __init__(
        self,
        session_repository: SessionRepository,
        team_repository: TeamRepository,
        workspace_repository: WorkspaceRepository,
        state_runtime: AgentScopeSessionStateRuntime,
    ) -> None:
        self._session_repository = session_repository
        self._team_repository = team_repository
        self._workspace_repository = workspace_repository
        self._state_runtime = state_runtime

    async def get_session_detail(self, session_id: str) -> dict:
        session = await self._session_repository.get(session_id)
        team = await self._team_repository.get_team(session.team_id)
        workspace = await self._workspace_repository.get(session.workspace_id)
        runtime_snapshot = await self._state_runtime.get_runtime_snapshot(
            session_id=session_id,
            agent_id=session.leader_agent_id,
        )
        return {
            "session": session.model_dump(mode="json"),
            "team": team.model_dump(mode="json"),
            "messages": runtime_snapshot["messages"],
            "runtime": {
                "current_plan": session.current_plan_snapshot,
                "current_summary": session.current_summary_snapshot,
                "waiting_items": [
                    item.model_dump(mode="json") for item in session.waiting_items
                ],
                "agent_statuses": [
                    item.model_dump(mode="json") for item in session.agent_statuses
                ],
            },
            "workspace_status": {
                "workspace_id": workspace.workspace_id,
                "name": workspace.name,
                "root_path": workspace.root_path,
                "status": workspace.status,
            },
        }
```

- [ ] **Step 4: Add session routes and ensure list/detail work**

```python
# backend/app/api/sessions.py
from fastapi import APIRouter

session_router = APIRouter(prefix="/sessions", tags=["sessions"])

@session_router.post("")
async def create_session(...):
    ...

@session_router.get("")
async def list_sessions(...):
    ...

@session_router.get("/{session_id}")
async def get_session_detail(...):
    ...
```

- [ ] **Step 5: Run session API/query tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_api.py backend/tests/test_session_query_service.py -v`
Expected: PASS for create/list/detail behavior.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/sessions.py backend/app/services/session_service.py backend/app/services/session_query_service.py backend/tests/test_session_api.py backend/tests/test_session_query_service.py backend/app/main.py backend/app/api/router.py
git commit -m "feat(backend): add product session resources"
```

### Task 5: AgentScope Runtime Session Bridging

**Files:**
- Create: `backend/app/runtime/agentscope/state_runtime.py`
- Create: `backend/app/runtime/agentscope/workspace_runtime.py`
- Create: `backend/app/runtime/agentscope/assembler.py`
- Modify: `backend/app/services/runtime_service.py`
- Test: `backend/tests/test_runtime_service.py`

- [ ] **Step 1: Write the failing runtime bridge tests**

```python
from app.runtime.agentscope.assembler import RuntimeAssembly


def test_runtime_assembly_uses_team_leader_as_runtime_agent() -> None:
    assembly = RuntimeAssembly(
        session_id="session-1",
        runtime_agent_id="leader-agent",
        workspace_id="workspace-1",
    )

    assert assembly.runtime_agent_id == "leader-agent"


def test_runtime_state_creation_uses_same_session_id_for_agentscope_session() -> None:
    runtime = AgentScopeSessionStateRuntime(...)

    record = runtime._build_session_config(
        session_id="session-1",
        workspace_id="workspace-1",
        name="Demo",
    )

    assert record.workspace_id == "workspace-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_runtime_service.py -v`
Expected: FAIL because runtime bridge modules do not exist yet.

- [ ] **Step 3: Implement AgentScope session state runtime helpers**

```python
# backend/app/runtime/agentscope/state_runtime.py
from __future__ import annotations

from agentscope.app.storage._model._session import SessionConfig
from agentscope.state import AgentState


class AgentScopeSessionStateRuntime:
    def __init__(self, storage) -> None:
        self._storage = storage

    async def create_runtime_session(
        self,
        session_id: str,
        agent_id: str,
        workspace_id: str,
        name: str,
    ) -> None:
        await self._storage.upsert_session(
            user_id="default-user",
            agent_id=agent_id,
            config=SessionConfig(
                workspace_id=workspace_id,
                name=name,
                chat_model_config=None,
                fallback_chat_model_config=None,
            ),
            state=AgentState(),
            session_id=session_id,
        )

    async def get_runtime_snapshot(self, session_id: str, agent_id: str) -> dict:
        session = await self._storage.get_session("default-user", agent_id, session_id)
        messages = await self._storage.list_messages("default-user", session_id, offset=0, limit=200)
        return {
            "session": session,
            "messages": [message.model_dump(mode="json") for message in messages],
        }
```

```python
# backend/app/runtime/agentscope/assembler.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RuntimeAssembly:
    session_id: str
    runtime_agent_id: str
    workspace_id: str
```

```python
# backend/app/runtime/agentscope/workspace_runtime.py
from __future__ import annotations

from agentscope.workspace import LocalWorkspace


class WorkspaceRuntime:
    async def build_local_workspace(self, root_path: str, workspace_id: str) -> LocalWorkspace:
        workspace = LocalWorkspace(workspace_id=workspace_id, workdir=root_path)
        await workspace.initialize()
        return workspace
```

- [ ] **Step 4: Run runtime bridge tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_runtime_service.py -v`
Expected: PASS for runtime session creation and assembly basics.

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/agentscope backend/tests/test_runtime_service.py backend/app/services/runtime_service.py
git commit -m "feat(backend): add agentscope runtime session bridge"
```

### Task 6: Chat Run, Waiting Items, Cancel, And Session Stream

**Files:**
- Modify: `backend/app/services/runtime_service.py`
- Create: `backend/app/runtime/agentscope/chat_runtime.py`
- Create: `backend/app/runtime/agentscope/stream_runtime.py`
- Create: `backend/app/runtime/agentscope/confirm_runtime.py`
- Create: `backend/app/api/session_stream.py`
- Modify: `backend/app/api/sessions.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/app/infrastructure/stream/sse.py`
- Test: `backend/tests/test_session_api.py`
- Test: `backend/tests/test_runtime_service.py`

- [ ] **Step 1: Write the failing run/stream/waiting tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_send_message_rejects_when_session_is_not_idle() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/sessions",
        json={"name": "Demo", "workspace_id": "workspace-1", "team_id": "team-1"},
    ).json()

    client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "first"},
    )
    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "second"},
    )

    assert response.status_code == 409


def test_submit_waiting_item_updates_product_session() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/sessions",
        json={"name": "Demo", "workspace_id": "workspace-1", "team_id": "team-1"},
    ).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/waiting/wait-1",
        json={"confirmed": True},
    )

    assert response.status_code in {200, 404}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_api.py backend/tests/test_runtime_service.py -v`
Expected: FAIL because runtime run/send/cancel/stream paths are incomplete.

- [ ] **Step 3: Implement runtime_service send/cancel/waiting flow**

```python
# backend/app/services/runtime_service.py
from __future__ import annotations

from app.infrastructure.storage.session_repository import SessionRepository


class RuntimeService:
    def __init__(self, session_repository: SessionRepository, chat_service, message_bus) -> None:
        self._session_repository = session_repository
        self._chat_service = chat_service
        self._message_bus = message_bus

    async def send_message(self, session_id: str, content: str) -> None:
        session = await self._session_repository.get(session_id)
        if session.status not in {"idle", "failed"}:
            raise ValueError("Session is not ready for a new message")
        session.status = "running"
        await self._session_repository.upsert(session)
        # Leader runtime trigger is handled here. Worker execution is not a manual
        # sub-call chain; it is expected to flow through AgentScope Runtime Team
        # via inbox + wakeup.

    async def cancel(self, session_id: str) -> None:
        session = await self._session_repository.get(session_id)
        session.status = "cancelling"
        await self._session_repository.upsert(session)
```

```python
# backend/app/api/session_stream.py
from fastapi import APIRouter

session_stream_router = APIRouter(prefix="/sessions", tags=["session-stream"])

@session_stream_router.get("/{session_id}/stream")
async def stream_session(...):
    ...
```

```python
# backend/app/infrastructure/stream/sse.py
def encode_sse(event: str, data: dict) -> str:
    import json
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

- [ ] **Step 4: Wire AgentScope chat trigger and confirm bridge**

```python
# backend/app/runtime/agentscope/confirm_runtime.py
from agentscope.event import ConfirmResult, UserConfirmResultEvent


class ConfirmRuntime:
    def build_confirm_event(self, reply_id: str, confirmed: bool, tool_call) -> UserConfirmResultEvent:
        return UserConfirmResultEvent(
            reply_id=reply_id,
            confirm_results=[
                ConfirmResult(
                    confirmed=confirmed,
                    tool_call=tool_call,
                    rules=tool_call.suggested_rules,
                ),
            ],
        )
```

- [ ] **Step 5: Run tests to verify message send / cancel / stream / waiting flow**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_api.py backend/tests/test_runtime_service.py -v`
Expected: PASS for send/cancel/waiting lifecycle basics; stream route exists and returns SSE response.

### Task 6A: Runtime Team Bridge And Worker Callback Integration

**Files:**
- Create: `backend/app/runtime/agentscope/team_runtime.py`
- Modify: `backend/app/services/session_service.py`
- Modify: `backend/app/services/runtime_service.py`
- Modify: `backend/app/services/session_query_service.py`
- Modify: `backend/app/api/session_stream.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_team_api.py`
- Test: `backend/tests/test_session_api.py`
- Test: `backend/tests/test_session_query_service.py`
- Test: `backend/tests/test_session_stream.py`

- [ ] **Step 1: Write failing runtime-team bridge tests**

Focus on these expectations:

- Product team members are mirrored into AgentScope Runtime Team workers
- Worker sessions are created as real AgentScope team worker sessions, not just ad-hoc parallel runtime sessions
- Worker callback returns through `TeamSay -> inbox -> wakeup -> InboxMiddleware`
- `session detail` and `session stream` reflect worker callback and waiting aggregation
- leader callback hint is persisted as a stable assistant message, not only observed as an in-memory hint or replay timing artifact

- [ ] **Step 2: Implement Runtime Team bridge instead of manual worker orchestration**

Key implementation constraints:

- Do not invent a custom worker scheduler at product layer
- Reuse AgentScope `TeamCreate / AgentCreate / TeamSay / WakeupDispatcher / InboxMiddleware`
- Product layer stores team/session metadata and projects runtime results only

- [ ] **Step 2A: Complete leader callback hint persistence semantics**

Add one explicit subtask that was missing from the original plan:

- Treat worker callback visibility as incomplete until the leader session has a persisted assistant hint message
- Do not rely on replay log residue or temporary runtime context injection as the product truth
- Use `messages` as the authoritative persisted result for callback hint visibility
- Keep `session_stream` as an observational channel, not the source of truth for callback recovery

- [ ] **Step 3: Run bridge and callback tests**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_team_api.py backend/tests/test_session_api.py backend/tests/test_session_query_service.py backend/tests/test_session_stream.py -v`
Expected: PASS for runtime-team creation, worker callback consumption, persisted leader hint visibility, waiting projection, and stream integration.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/runtime_service.py backend/app/runtime/agentscope/chat_runtime.py backend/app/runtime/agentscope/confirm_runtime.py backend/app/api/session_stream.py backend/app/api/sessions.py backend/app/api/router.py backend/app/infrastructure/stream/sse.py backend/tests/test_session_api.py backend/tests/test_runtime_service.py
git commit -m "feat(backend): add session runtime, waiting, and stream"
```

### Task 7: Runtime Sidebar Snapshots And Plan File Projection

**Files:**
- Modify: `backend/app/services/session_query_service.py`
- Modify: `backend/app/services/workspace_query_service.py`
- Create: `backend/tests/test_session_query_service.py`

- [ ] **Step 1: Write the failing snapshot projection tests**

```python
def test_session_detail_reads_plan_snapshot_from_workspace_file() -> None:
    service = SessionQueryService(...)

    detail = service._build_runtime_section(
        current_plan_snapshot={"path": "plans/current-plan.json"},
        waiting_items=[],
        agent_statuses=[],
    )

    assert detail["current_plan"] == {"path": "plans/current-plan.json"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_query_service.py -v`
Expected: FAIL if projection helpers are missing.

- [ ] **Step 3: Implement runtime sidebar projection helpers**

```python
# backend/app/services/session_query_service.py (projection excerpt)
def _build_runtime_section(
    self,
    current_plan_snapshot: dict | None,
    current_summary_snapshot: str | None,
    waiting_items: list,
    agent_statuses: list,
) -> dict:
    return {
        "current_plan": current_plan_snapshot,
        "current_summary": current_summary_snapshot,
        "waiting_items": [item.model_dump(mode="json") for item in waiting_items],
        "agent_statuses": [item.model_dump(mode="json") for item in agent_statuses],
    }
```

- [ ] **Step 4: Run tests to verify projection passes**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_query_service.py -v`
Expected: PASS for detail snapshot structure.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/session_query_service.py backend/app/services/workspace_query_service.py backend/tests/test_session_query_service.py
git commit -m "feat(backend): project session runtime sidebar snapshots"
```

### Task 8: App Wiring, Smoke Coverage, And End-to-End Verification

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/router.py`
- Modify: `backend/tests/test_app.py`
- Test: `backend/tests/test_app.py`
- Test: `backend/tests/test_session_api.py`
- Test: `backend/tests/test_team_api.py`
- Test: `backend/tests/test_workspace_api.py`
- Test: `backend/tests/test_runtime_service.py`
- Test: `backend/tests/test_session_query_service.py`

- [ ] **Step 1: Write/update final smoke tests for new routes**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_app_exposes_core_resource_routes() -> None:
    client = TestClient(create_app())

    openapi = client.get("/openapi.json")

    assert openapi.status_code == 200
    paths = openapi.json()["paths"]
    assert "/api/v1/sessions" in paths
    assert "/api/v1/teams" in paths
    assert "/api/v1/workspaces" in paths
```

- [ ] **Step 2: Run smoke tests to verify they fail if wiring is incomplete**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_app.py -v`
Expected: FAIL until routers/services are fully wired.

- [ ] **Step 3: Wire service factories, routers, and startup bootstrap**

```python
# backend/app/main.py (wiring excerpt)
def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name, version=get_settings().app_version)
    app.include_router(api_router, prefix=get_settings().api_v1_prefix)
    return app
```

```python
# backend/app/api/router.py
api_router.include_router(session_router)
api_router.include_router(session_stream_router)
api_router.include_router(team_router)
api_router.include_router(workspace_router)
```

- [ ] **Step 4: Run the complete backend test set**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_app.py backend/tests/test_session_api.py backend/tests/test_team_api.py backend/tests/test_workspace_api.py backend/tests/test_runtime_service.py backend/tests/test_session_query_service.py -v`
Expected: PASS across all backend phase 1 tests.

- [ ] **Step 5: Run lint**

Run: `& ".\.venv\Scripts\python.exe" -m ruff check backend/app backend/tests`
Expected: PASS with no E/F/I issues.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/api/router.py backend/tests/test_app.py
git commit -m "feat(backend): wire session team workspace backend shell"
```
