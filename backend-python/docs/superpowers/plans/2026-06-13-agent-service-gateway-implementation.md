# Agent Service 与 Gateway Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前仓库 `backend-python` 收敛为 future `agent_service`，以 `SQLite` 替代 `InMemoryStore`，补齐 `source workspace`、`session workspace`、`session`、`domain event` 四类核心资源，并新增最小可运行的 `gateway_service` SSE 聚合骨架。

**Architecture:** 先在当前仓库内完成 `agent_service` 的资源模型、SQLite 持久化、session 入口与 domain event 最小闭环，保持现有 orchestrator/worker/runtime 主链路不被推翻。随后新增一个独立的最小 `gateway_service`，只负责前端聚合查询与 SSE 事件转发，不在第一阶段承担新的领域编排逻辑。

**Tech Stack:** Python 3.x, FastAPI, Pydantic, sqlite3, pytest

---

## 约束与执行说明

- 本计划遵守用户偏好：**不做分步 commit**，只在整轮实现与验证完成后做一次总提交。
- 当前代码基于 `InMemoryStore` 运行；本计划的目标是把正式存储切换到 `SQLite`。
- 现有 `AgentRunInputService`、`RuntimeAssembler`、`LoopEngine`、`delegate_tool`、`workspace_session` 保留并复用。
- 第一阶段不实现复杂迁移系统，不引入 ORM，不上 MQ。
- 所有验证命令使用虚拟环境 Python：

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest ...
```

## 文件结构映射

### 当前仓库内新增或修改的核心文件

- Create: `app/config.py` 中如有需要补充 SQLite 配置项
- Create: `app/database/sqlite.py`
- Create: `app/database/schema.py`
- Create: `app/database/connection.py`
- Create: `app/models/source_workspace.py`
- Create: `app/models/session_workspace.py`
- Create: `app/models/session.py`
- Create: `app/models/domain_event.py`
- Create: `app/repositories/source_workspace_repository.py`
- Create: `app/repositories/session_workspace_repository.py`
- Create: `app/repositories/session_repository.py`
- Create: `app/repositories/domain_event_repository.py`
- Create: `app/schemas/source_workspace.py`
- Create: `app/schemas/session_workspace.py`
- Create: `app/schemas/session.py`
- Create: `app/schemas/domain_event.py`
- Create: `app/services/session_service.py`
- Create: `app/services/source_workspace_service.py`
- Create: `app/services/session_workspace_service.py`
- Create: `app/api/source_workspace.py`
- Create: `app/api/session_workspace.py`
- Create: `app/api/session.py`
- Modify: `app/models/agent_run.py`
- Modify: `app/models/subtask.py`
- Modify: `app/repositories/agent_run_repository.py`
- Modify: `app/repositories/subtask_repository.py`
- Modify: `app/repositories/input_event_repository.py`
- Modify: `app/repositories/plan_repository.py`
- Modify: `app/services/agent_run_create_service.py`
- Modify: `app/services/agent_run_input_service.py`
- Modify: `app/tools/delegate_tool.py`
- Modify: `app/database/bootstrap.py`
- Modify: `app/main.py`
- Modify: `app/api/agent_run_create.py`
- Modify: `app/api/agent_run_input.py`

### gateway_service 最小骨架建议文件

- Create: `gateway-service-python/main.py`
- Create: `gateway-service-python/app/__init__.py`
- Create: `gateway-service-python/app/config.py`
- Create: `gateway-service-python/app/client/agent_service_client.py`
- Create: `gateway-service-python/app/api/workspace_page.py`
- Create: `gateway-service-python/app/api/session_page.py`
- Create: `gateway-service-python/app/api/session_stream.py`
- Create: `gateway-service-python/tests/test_app.py`
- Create: `gateway-service-python/tests/test_session_stream.py`

### 测试文件建议

- Create: `tests/test_sqlite_bootstrap.py`
- Create: `tests/test_source_workspace_repository.py`
- Create: `tests/test_session_workspace_repository.py`
- Create: `tests/test_session_repository.py`
- Create: `tests/test_domain_event_repository.py`
- Create: `tests/test_session_service.py`
- Create: `tests/test_source_workspace_service.py`
- Create: `tests/test_session_workspace_service.py`
- Create: `tests/test_session_api.py`
- Modify: `tests/test_agent_run_create.py`
- Modify: `tests/test_agent_run_input.py`
- Modify: `tests/test_delegate_tool.py`
- Modify: `tests/test_delegate_chain_internal_code_tool.py`
- Modify: `tests/test_delegate_chain_internal_bash_tool.py`
- Modify: `tests/test_bootstrap.py`

## 实施拆分

本实现计划拆成两个连续子项目：

1. 当前仓库内的 future `agent_service`
2. 新增最小 `gateway_service`

这样每一段都能形成可验证的软件增量，不会把数据库改造、资源建模、实时流、第二服务骨架全部搅成一个大任务。

### Task 1: 引入 SQLite 基础设施并替代 InMemoryStore 作为正式存储

**Files:**
- Create: `app/database/sqlite.py`
- Create: `app/database/schema.py`
- Create: `app/database/connection.py`
- Modify: `app/config.py`
- Modify: `app/database/bootstrap.py`
- Test: `tests/test_sqlite_bootstrap.py`
- Test: `tests/test_bootstrap.py`

- [ ] **Step 1: 写出 SQLite 初始化失败测试**

```python
from pathlib import Path

from app.database.sqlite import SQLiteDatabase


def test_sqlite_database_creates_file_and_connection(tmp_path: Path) -> None:
    db_path = tmp_path / "agenthub.db"

    database = SQLiteDatabase(str(db_path))
    conn = database.connect()

    assert db_path.exists()
    assert conn is not None
```

- [ ] **Step 2: 运行单测确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_sqlite_bootstrap.py::test_sqlite_database_creates_file_and_connection -v
```

Expected:

- FAIL，提示 `app.database.sqlite` 或 `SQLiteDatabase` 不存在。

- [ ] **Step 3: 写最小 SQLite 连接实现**

```python
# app/database/sqlite.py
from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteDatabase:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        return sqlite3.connect(self.db_path)
```

- [ ] **Step 4: 写 schema 初始化测试**

```python
from pathlib import Path

from app.database.schema import initialize_schema
from app.database.sqlite import SQLiteDatabase


def test_initialize_schema_creates_core_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "agenthub.db"
    conn = SQLiteDatabase(str(db_path)).connect()

    initialize_schema(conn)

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {row[0] for row in rows}

    assert "agents" in names
    assert "agent_runs" in names
    assert "source_workspaces" in names
    assert "session_workspaces" in names
    assert "sessions" in names
    assert "domain_events" in names
```

- [ ] **Step 5: 运行 schema 测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_sqlite_bootstrap.py::test_initialize_schema_creates_core_tables -v
```

Expected:

- FAIL，提示 `initialize_schema` 不存在或表未创建。

- [ ] **Step 6: 写最小 schema 初始化实现**

```python
# app/database/schema.py
from __future__ import annotations

import sqlite3


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agents (
            agent_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_runs (
            run_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS input_events (
            input_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS subtasks (
            subtask_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS plans (
            run_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_workspaces (
            source_workspace_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS session_workspaces (
            session_workspace_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS domain_events (
            event_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        """
    )
    conn.commit()
```

- [ ] **Step 7: 配置 bootstrap 改为初始化 SQLite**

```python
# app/database/connection.py
from __future__ import annotations

from app.config import get_settings
from app.database.sqlite import SQLiteDatabase


def get_connection():
    settings = get_settings()
    return SQLiteDatabase(settings.sqlite_db_path).connect()
```

```python
# app/database/bootstrap.py
from __future__ import annotations

from app.config import get_settings
from app.database.schema import initialize_schema
from app.database.sqlite import SQLiteDatabase


def bootstrap_memory_store() -> None:
    settings = get_settings()
    conn = SQLiteDatabase(settings.sqlite_db_path).connect()
    initialize_schema(conn)
    conn.close()
```

```python
# app/config.py 新增字段示意
sqlite_db_path: str = "./.AgentHub/agenthub.db"
```

- [ ] **Step 8: 运行 Task 1 相关测试**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_sqlite_bootstrap.py tests/test_bootstrap.py -q
```

Expected:

- PASS

### Task 2: 为现有 repository 提供 SQLite 持久化能力

**Files:**
- Modify: `app/repositories/agent_run_repository.py`
- Modify: `app/repositories/input_event_repository.py`
- Modify: `app/repositories/subtask_repository.py`
- Modify: `app/repositories/plan_repository.py`
- Test: `tests/test_agent_run_create.py`
- Test: `tests/test_agent_run_input.py`
- Test: `tests/test_delegate_tool.py`

- [ ] **Step 1: 写 repository 持久化回归测试**

```python
from uuid import uuid4

from app.models.agent_run import AgentRunModel
from app.repositories.agent_run_repository import AgentRunRepository


def test_agent_run_repository_round_trips_sqlite_record() -> None:
    repository = AgentRunRepository()
    run = AgentRunModel(
        run_id=uuid4(),
        agent_id=uuid4(),
        role="orchestrator",
        agent_kind="orchestrator",
        workspace_id=uuid4(),
        status="created",
    )

    repository.create(run)
    loaded = repository.get_by_id(run.run_id)

    assert loaded is not None
    assert loaded.run_id == run.run_id
    assert loaded.status == "created"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_agent_run_create.py::test_agent_run_repository_round_trips_sqlite_record -v
```

Expected:

- FAIL，现有 repository 仍依赖 `STORE`。

- [ ] **Step 3: 为 repository 写统一 JSON payload 持久化实现**

```python
# app/repositories/agent_run_repository.py 核心方向
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.database.connection import get_connection
from app.models.agent_run import AgentRunModel


class AgentRunRepository:
    def create(self, agent_run: AgentRunModel) -> AgentRunModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO agent_runs (run_id, payload) VALUES (?, ?)",
            (str(agent_run.run_id), agent_run.model_dump_json()),
        )
        conn.commit()
        return agent_run

    def get_by_id(self, run_id: UUID) -> AgentRunModel | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT payload FROM agent_runs WHERE run_id = ?",
            (str(run_id),),
        ).fetchone()
        if row is None:
            return None
        return AgentRunModel.model_validate_json(row[0])
```

- [ ] **Step 4: 对 `input_event`、`subtask`、`plan` repository 做同样改造**

```python
# 三个 repository 统一模式
conn.execute(
    "INSERT OR REPLACE INTO <table> (<id>, payload) VALUES (?, ?)",
    (str(model_id), model.model_dump_json()),
)
```

关键要求：

- 读取时统一使用 `model_validate_json`
- 更新时保留当前 repository 方法签名
- 不在这一轮引入 SQL 查询优化

- [ ] **Step 5: 运行现有 run/input/delegate 测试回归**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_agent_run_create.py tests/test_agent_run_input.py tests/test_delegate_tool.py tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py -q
```

Expected:

- PASS

### Task 3: 增加 source workspace / session workspace / session / domain event 模型与 repository

**Files:**
- Create: `app/models/source_workspace.py`
- Create: `app/models/session_workspace.py`
- Create: `app/models/session.py`
- Create: `app/models/domain_event.py`
- Create: `app/repositories/source_workspace_repository.py`
- Create: `app/repositories/session_workspace_repository.py`
- Create: `app/repositories/session_repository.py`
- Create: `app/repositories/domain_event_repository.py`
- Test: `tests/test_source_workspace_repository.py`
- Test: `tests/test_session_workspace_repository.py`
- Test: `tests/test_session_repository.py`
- Test: `tests/test_domain_event_repository.py`

- [ ] **Step 1: 写 source workspace repository 测试**

```python
from pathlib import Path
from uuid import uuid4

from app.models.source_workspace import SourceWorkspaceModel
from app.repositories.source_workspace_repository import SourceWorkspaceRepository


def test_source_workspace_repository_creates_and_loads_record(tmp_path: Path) -> None:
    repository = SourceWorkspaceRepository()
    workspace = SourceWorkspaceModel(
        source_workspace_id=uuid4(),
        name="demo",
        root_path=str(tmp_path),
        status="ready",
    )

    repository.create(workspace)
    loaded = repository.get_by_id(workspace.source_workspace_id)

    assert loaded is not None
    assert loaded.name == "demo"
    assert loaded.status == "ready"
```

- [ ] **Step 2: 写 session workspace repository 测试**

```python
from pathlib import Path
from uuid import uuid4

from app.models.session_workspace import SessionWorkspaceModel
from app.repositories.session_workspace_repository import SessionWorkspaceRepository


def test_session_workspace_repository_lists_by_source_workspace(tmp_path: Path) -> None:
    repository = SessionWorkspaceRepository()
    source_workspace_id = uuid4()
    workspace = SessionWorkspaceModel(
        session_workspace_id=uuid4(),
        source_workspace_id=source_workspace_id,
        name="branch-a",
        root_path=str(tmp_path / "branch-a"),
        status="ready",
    )

    repository.create(workspace)
    items = repository.list_by_source_workspace_id(source_workspace_id)

    assert len(items) == 1
    assert items[0].name == "branch-a"
```

- [ ] **Step 3: 写 session 与 domain event repository 测试**

```python
from uuid import uuid4

from app.models.domain_event import DomainEventModel
from app.models.session import SessionModel
from app.repositories.domain_event_repository import DomainEventRepository
from app.repositories.session_repository import SessionRepository


def test_session_repository_creates_active_session() -> None:
    repository = SessionRepository()
    session = SessionModel(
        session_id=uuid4(),
        session_workspace_id=uuid4(),
        title="demo session",
        status="active",
    )

    repository.create(session)
    loaded = repository.get_by_id(session.session_id)

    assert loaded is not None
    assert loaded.status == "active"


def test_domain_event_repository_lists_session_events_in_sequence() -> None:
    repository = DomainEventRepository()
    session_id = uuid4()
    first = DomainEventModel(
        event_id=uuid4(),
        session_id=session_id,
        session_workspace_id=uuid4(),
        event_type="session.message.appended",
        event_scope="main_timeline",
        sequence_no=1,
        payload={"content": "hello"},
    )
    second = DomainEventModel(
        event_id=uuid4(),
        session_id=session_id,
        session_workspace_id=first.session_workspace_id,
        event_type="plan.updated",
        event_scope="main_timeline",
        sequence_no=2,
        payload={"summary": "updated"},
    )

    repository.create(first)
    repository.create(second)
    items = repository.list_by_session_id(session_id)

    assert [item.sequence_no for item in items] == [1, 2]
```

- [ ] **Step 4: 运行新模型测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_source_workspace_repository.py tests/test_session_workspace_repository.py tests/test_session_repository.py tests/test_domain_event_repository.py -q
```

Expected:

- FAIL，模型与 repository 尚不存在。

- [ ] **Step 5: 写四个最小模型**

```python
# app/models/source_workspace.py
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class SourceWorkspaceModel(BaseModel):
    source_workspace_id: UUID
    name: str
    root_path: str
    status: str = "ready"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

```python
# app/models/session_workspace.py
class SessionWorkspaceModel(BaseModel):
    session_workspace_id: UUID
    source_workspace_id: UUID
    name: str
    root_path: str
    status: str = "ready"
    origin_session_workspace_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

```python
# app/models/session.py
class SessionModel(BaseModel):
    session_id: UUID
    session_workspace_id: UUID
    title: str
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
```

```python
# app/models/domain_event.py
class DomainEventModel(BaseModel):
    event_id: UUID
    session_id: UUID
    session_workspace_id: UUID
    run_id: UUID | None = None
    subtask_id: UUID | None = None
    event_type: str
    event_scope: str
    payload: dict[str, object] = Field(default_factory=dict)
    sequence_no: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 6: 写四个最小 SQLite repository**

```python
# 模式示意：app/repositories/source_workspace_repository.py
from __future__ import annotations

from uuid import UUID

from app.database.connection import get_connection
from app.models.source_workspace import SourceWorkspaceModel


class SourceWorkspaceRepository:
    def create(self, workspace: SourceWorkspaceModel) -> SourceWorkspaceModel:
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO source_workspaces (source_workspace_id, payload) VALUES (?, ?)",
            (str(workspace.source_workspace_id), workspace.model_dump_json()),
        )
        conn.commit()
        return workspace
```

必需方法：

- `SourceWorkspaceRepository.create/get_by_id/list_all/update`
- `SessionWorkspaceRepository.create/get_by_id/list_by_source_workspace_id/update`
- `SessionRepository.create/get_by_id/update/list_by_session_workspace_id`
- `DomainEventRepository.create/list_by_session_id/next_sequence_no`

- [ ] **Step 7: 运行 Task 3 全部测试**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_source_workspace_repository.py tests/test_session_workspace_repository.py tests/test_session_repository.py tests/test_domain_event_repository.py -q
```

Expected:

- PASS

### Task 4: 将 agent_run 与 subtask 挂接到 session 语义

**Files:**
- Modify: `app/models/agent_run.py`
- Modify: `app/models/subtask.py`
- Modify: `app/services/agent_run_create_service.py`
- Modify: `app/tools/delegate_tool.py`
- Test: `tests/test_agent_run_create.py`
- Test: `tests/test_delegate_tool.py`

- [ ] **Step 1: 写 `agent_run` 挂接 `session_id` 的失败测试**

```python
from uuid import uuid4

from app.models.agent_run import AgentRunModel


def test_agent_run_model_keeps_session_id() -> None:
    session_id = uuid4()
    run = AgentRunModel(
        run_id=uuid4(),
        session_id=session_id,
        agent_id=uuid4(),
        role="orchestrator",
        agent_kind="orchestrator",
        workspace_id=uuid4(),
        status="created",
    )

    assert run.session_id == session_id
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_agent_run_create.py::test_agent_run_model_keeps_session_id -v
```

Expected:

- FAIL，`AgentRunModel` 没有 `session_id` 字段。

- [ ] **Step 3: 最小修改 `AgentRunModel` 与 `SubtaskModel`**

```python
# app/models/agent_run.py
class AgentRunModel(BaseModel):
    run_id: UUID
    session_id: UUID | None = None
    agent_id: UUID
    role: str | None = None
    agent_kind: str
    workspace_id: UUID
    ...
```

```python
# app/models/subtask.py
class SubtaskModel(BaseModel):
    subtask_id: UUID
    session_id: UUID | None = None
    root_run_id: UUID
    parent_run_id: UUID
    worker_run_id: UUID
    ...
```

- [ ] **Step 4: 修改 `AgentRunCreateService` 与 `delegate_tool` 在创建 run/subtask 时写入 `session_id`**

```python
# AgentRunCreateService 方向
agent_run = AgentRunModel(
    run_id=run_id,
    session_id=payload.session_id,
    ...
)
```

```python
# delegate_tool 方向
worker_run = AgentRunModel(
    run_id=worker_run_id,
    session_id=parent_run.session_id,
    ...
)
subtask = SubtaskModel(
    subtask_id=subtask_id,
    session_id=parent_run.session_id,
    ...
)
```

- [ ] **Step 5: 运行 run/delegate 相关测试**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_agent_run_create.py tests/test_delegate_tool.py tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py -q
```

Expected:

- PASS

### Task 5: 新增 source workspace / session workspace / session 服务层

**Files:**
- Create: `app/services/source_workspace_service.py`
- Create: `app/services/session_workspace_service.py`
- Create: `app/services/session_service.py`
- Test: `tests/test_source_workspace_service.py`
- Test: `tests/test_session_workspace_service.py`
- Test: `tests/test_session_service.py`

- [ ] **Step 1: 写 source workspace service 测试**

```python
from pathlib import Path

from app.schemas.source_workspace import SourceWorkspaceCreateRequest
from app.services.source_workspace_service import SourceWorkspaceService


def test_create_source_workspace_persists_ready_record(tmp_path: Path) -> None:
    service = SourceWorkspaceService()
    response = service.create(
        SourceWorkspaceCreateRequest(name="demo", root_path=str(tmp_path))
    )

    assert response.name == "demo"
    assert response.status == "ready"
```

- [ ] **Step 2: 写 session workspace service 测试**

```python
from pathlib import Path
from uuid import uuid4

from app.schemas.session_workspace import SessionWorkspaceCreateRequest
from app.services.session_workspace_service import SessionWorkspaceService


def test_create_session_workspace_for_source_workspace(tmp_path: Path) -> None:
    service = SessionWorkspaceService()
    response = service.create(
        SessionWorkspaceCreateRequest(
            source_workspace_id=uuid4(),
            name="branch-a",
            root_path=str(tmp_path / "branch-a"),
        )
    )

    assert response.name == "branch-a"
    assert response.status == "ready"
```

- [ ] **Step 3: 写 session service 测试**

```python
from uuid import uuid4

from app.models.session_workspace import SessionWorkspaceModel
from app.repositories.session_workspace_repository import SessionWorkspaceRepository
from app.schemas.session import SessionCreateRequest
from app.services.session_service import SessionService


def test_create_session_attaches_session_workspace() -> None:
    session_workspace = SessionWorkspaceModel(
        session_workspace_id=uuid4(),
        source_workspace_id=uuid4(),
        name="branch-a",
        root_path="E:/workspace/branch-a",
        status="ready",
    )
    SessionWorkspaceRepository().create(session_workspace)

    service = SessionService()
    response = service.create(
        SessionCreateRequest(
            session_workspace_id=session_workspace.session_workspace_id,
            title="demo session",
        )
    )

    assert response.status == "active"
    updated = SessionWorkspaceRepository().get_by_id(session_workspace.session_workspace_id)
    assert updated is not None
    assert updated.status == "attached"
```

- [ ] **Step 4: 运行 service 测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_source_workspace_service.py tests/test_session_workspace_service.py tests/test_session_service.py -q
```

Expected:

- FAIL，service 与 schema 尚不存在。

- [ ] **Step 5: 写最小请求/响应 schema**

```python
# app/schemas/source_workspace.py
class SourceWorkspaceCreateRequest(BaseModel):
    name: str
    root_path: str


class SourceWorkspaceResponse(BaseModel):
    source_workspace_id: UUID
    name: str
    root_path: str
    status: str
```

```python
# app/schemas/session_workspace.py
class SessionWorkspaceCreateRequest(BaseModel):
    source_workspace_id: UUID
    name: str
    root_path: str
```

```python
# app/schemas/session.py
class SessionCreateRequest(BaseModel):
    session_workspace_id: UUID
    title: str
```

- [ ] **Step 6: 写三个最小 service 实现**

```python
# app/services/session_service.py 方向
class SessionService:
    def create(self, payload: SessionCreateRequest) -> SessionResponse:
        session_workspace = self.session_workspace_repository.get_by_id(payload.session_workspace_id)
        if session_workspace is None:
            raise ValueError("session workspace not found")
        if session_workspace.status != "ready":
            raise ValueError("session workspace is not available")

        session = SessionModel(
            session_id=uuid4(),
            session_workspace_id=payload.session_workspace_id,
            title=payload.title,
            status="active",
        )
        self.session_repository.create(session)
        self.session_workspace_repository.update(
            session_workspace.model_copy(update={"status": "attached"})
        )
        return SessionResponse.model_validate(session.model_dump())
```

要求：

- `SourceWorkspaceService.create()` 创建 `ready` 状态记录
- `SessionWorkspaceService.create()` 创建 `ready` 状态记录
- `SessionService.create()` 校验 `session_workspace` 状态并设置为 `attached`
- `SessionService.delete()` 将 session 标记为 `deleted` 并释放 workspace 为 `ready`

- [ ] **Step 7: 运行服务层测试**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_source_workspace_service.py tests/test_session_workspace_service.py tests/test_session_service.py -q
```

Expected:

- PASS

### Task 6: 为 session 主链路接入最小 domain event 记录

**Files:**
- Modify: `app/services/session_service.py`
- Modify: `app/services/agent_run_input_service.py`
- Create: `app/schemas/domain_event.py`
- Test: `tests/test_domain_event_repository.py`
- Test: `tests/test_session_service.py`
- Modify: `tests/test_agent_run_input.py`

- [ ] **Step 1: 写 session 创建写入事件的测试**

```python
from app.repositories.domain_event_repository import DomainEventRepository


def test_create_session_emits_session_message_event() -> None:
    repository = DomainEventRepository()
    items = repository.list_by_session_id(created_session_id)

    assert items[0].event_type == "session.message.appended"
```
```

注：这里的 `created_session_id` 需要复用前一个测试里创建 session 的那段逻辑，不要引入 fixture 魔法，直接在同一个测试函数里创建即可。

- [ ] **Step 2: 写 run 输入后产生事件的测试**

```python
def test_agent_run_input_persists_domain_event_for_user_message() -> None:
    response = service.input(run_id=run.run_id, payload=payload)

    events = DomainEventRepository().list_by_session_id(run.session_id)

    assert response.status == "accepted"
    assert any(event.event_type == "session.message.appended" for event in events)
```

- [ ] **Step 3: 运行测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_session_service.py tests/test_agent_run_input.py -q
```

Expected:

- FAIL，domain event 尚未在 service 中写入。

- [ ] **Step 4: 最小实现 domain event service 写入逻辑**

```python
# SessionService.create() 中追加
sequence_no = self.domain_event_repository.next_sequence_no(session.session_id)
self.domain_event_repository.create(
    DomainEventModel(
        event_id=uuid4(),
        session_id=session.session_id,
        session_workspace_id=session.session_workspace_id,
        event_type="session.message.appended",
        event_scope="main_timeline",
        sequence_no=sequence_no,
        payload={"content": session.title, "kind": "session_created"},
    )
)
```

```python
# AgentRunInputService.input() 中追加
if runtime_bundle.agent_run.session_id is not None and input_event.type.value == "user_input":
    sequence_no = self.domain_event_repository.next_sequence_no(runtime_bundle.agent_run.session_id)
    self.domain_event_repository.create(
        DomainEventModel(
            event_id=uuid4(),
            session_id=runtime_bundle.agent_run.session_id,
            session_workspace_id=runtime_bundle.agent_run.workspace_id,
            run_id=runtime_bundle.agent_run.run_id,
            event_type="session.message.appended",
            event_scope="main_timeline",
            sequence_no=sequence_no,
            payload={"content": self._build_user_message_content(input_event)},
        )
    )
```

- [ ] **Step 5: 运行 domain event 相关测试**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_domain_event_repository.py tests/test_session_service.py tests/test_agent_run_input.py -q
```

Expected:

- PASS

### Task 7: 新增 source workspace / session workspace / session API

**Files:**
- Create: `app/api/source_workspace.py`
- Create: `app/api/session_workspace.py`
- Create: `app/api/session.py`
- Modify: `app/main.py`
- Test: `tests/test_session_api.py`
- Modify: `tests/test_app.py`

- [ ] **Step 1: 写 session API 集成测试**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_create_session_endpoint_returns_active_session() -> None:
    client = TestClient(create_app())

    source_workspace = client.post(
        "/source-workspaces",
        json={"name": "demo", "root_path": "E:/workspace/demo"},
    ).json()
    session_workspace = client.post(
        "/session-workspaces",
        json={
            "source_workspace_id": source_workspace["source_workspace_id"],
            "name": "branch-a",
            "root_path": "E:/workspace/demo-branch-a",
        },
    ).json()

    response = client.post(
        "/sessions",
        json={
            "session_workspace_id": session_workspace["session_workspace_id"],
            "title": "demo session",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_session_api.py::test_create_session_endpoint_returns_active_session -v
```

Expected:

- FAIL，相关 router 尚不存在。

- [ ] **Step 3: 写三个最小 API router**

```python
# app/api/source_workspace.py
router = APIRouter(prefix="/source-workspaces", tags=["source-workspaces"])


@router.post("")
def create_source_workspace(payload: SourceWorkspaceCreateRequest):
    return get_service().create(payload)
```

```python
# app/api/session_workspace.py
router = APIRouter(prefix="/session-workspaces", tags=["session-workspaces"])


@router.post("")
def create_session_workspace(payload: SessionWorkspaceCreateRequest):
    return get_service().create(payload)
```

```python
# app/api/session.py
router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("")
def create_session(payload: SessionCreateRequest):
    return get_service().create(payload)


@router.post("/{session_id}/delete")
def delete_session(session_id: UUID):
    return get_service().delete(session_id)
```

- [ ] **Step 4: 在 `app/main.py` 注册新 router**

```python
app.include_router(source_workspace_router)
app.include_router(session_workspace_router)
app.include_router(session_router)
```

- [ ] **Step 5: 运行 API 测试**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_session_api.py tests/test_app.py -q
```

Expected:

- PASS

### Task 8: 将现有 agent-run 入口收编到 session 语义

**Files:**
- Modify: `app/schemas/agent_run_create.py`
- Modify: `app/services/agent_run_create_service.py`
- Modify: `app/api/agent_run_create.py`
- Modify: `tests/test_agent_run_create.py`
- Modify: `tests/test_agent_run_input.py`

- [ ] **Step 1: 写 `AgentRunCreateRequest` 需要 `session_id` 的测试**

```python
from uuid import uuid4

from app.schemas.agent_run_create import AgentRunCreateRequest


def test_agent_run_create_request_accepts_session_id() -> None:
    payload = AgentRunCreateRequest(
        agent_id=uuid4(),
        session_id=uuid4(),
        workspace_id=uuid4(),
        metadata={},
    )

    assert payload.session_id is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_agent_run_create.py::test_agent_run_create_request_accepts_session_id -v
```

Expected:

- FAIL，schema 尚无 `session_id`。

- [ ] **Step 3: 修改 schema 与 service**

```python
# app/schemas/agent_run_create.py
class AgentRunCreateRequest(BaseModel):
    agent_id: UUID
    session_id: UUID
    workspace_id: UUID
    metadata: dict[str, object] = Field(default_factory=dict)
```

```python
# app/services/agent_run_create_service.py
agent_run = AgentRunModel(
    run_id=run_id,
    session_id=payload.session_id,
    ...
)
```

- [ ] **Step 4: 运行 run create/input 测试回归**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_agent_run_create.py tests/test_agent_run_input.py -q
```

Expected:

- PASS

### Task 9: 新增最小 gateway_service 骨架与 SSE 事件流

**Files:**
- Create: `gateway-service-python/main.py`
- Create: `gateway-service-python/app/config.py`
- Create: `gateway-service-python/app/client/agent_service_client.py`
- Create: `gateway-service-python/app/api/workspace_page.py`
- Create: `gateway-service-python/app/api/session_page.py`
- Create: `gateway-service-python/app/api/session_stream.py`
- Create: `gateway-service-python/tests/test_app.py`
- Create: `gateway-service-python/tests/test_session_stream.py`

- [ ] **Step 1: 写 gateway app 启动测试**

```python
from fastapi.testclient import TestClient

from main import create_app


def test_gateway_app_healthz() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 写 SSE stream 测试**

```python
from fastapi.testclient import TestClient

from main import create_app


def test_session_stream_returns_text_event_stream(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.client.agent_service_client.AgentServiceClient.list_session_events",
        lambda self, session_id, after_sequence_no=None: [
            {
                "sequence_no": 1,
                "event_type": "session.message.appended",
                "payload": {"content": "hello"},
            }
        ],
    )

    client = TestClient(create_app())
    response = client.get("/sessions/00000000-0000-0000-0000-000000000001/stream")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "session.message.appended" in response.text
```

- [ ] **Step 3: 运行 gateway 测试确认失败**

Run:

```powershell
Test-Path -LiteralPath "E:\Github\AgentHub-weon\gateway-service-python"
```

Expected:

- `False`

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway-service-python/tests/test_app.py gateway-service-python/tests/test_session_stream.py -q
```

Expected:

- FAIL，gateway service 文件不存在。

- [ ] **Step 4: 创建最小 gateway app 与客户端抽象**

```python
# gateway-service-python/main.py
from fastapi import FastAPI

from app.api.session_page import router as session_page_router
from app.api.session_stream import router as session_stream_router
from app.api.workspace_page import router as workspace_page_router


def create_app() -> FastAPI:
    app = FastAPI(title="gateway_service", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(workspace_page_router)
    app.include_router(session_page_router)
    app.include_router(session_stream_router)
    return app


app = create_app()
```

```python
# gateway-service-python/app/client/agent_service_client.py
class AgentServiceClient:
    def list_session_events(self, session_id: str, after_sequence_no: int | None = None) -> list[dict]:
        return []
```

- [ ] **Step 5: 写最小 workspace/session page 与 SSE router**

```python
# gateway-service-python/app/api/session_stream.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.client.agent_service_client import AgentServiceClient

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/{session_id}/stream")
def session_stream(session_id: str):
    client = AgentServiceClient()
    events = client.list_session_events(session_id)

    def iterator():
        for item in events:
            yield (
                f"id: {item['sequence_no']}\n"
                f"event: {item['event_type']}\n"
                f"data: {item['payload']}\n\n"
            )

    return StreamingResponse(iterator(), media_type="text/event-stream")
```

要求：

- `workspace_page.py` 先固定返回以下结构：

```python
{
    "source_workspace": None,
    "session_workspaces": [],
}
```

- `session_page.py` 先固定返回以下结构：

```python
{
    "session": None,
    "main_timeline": [],
    "subtasks": [],
    "workspace_panel": {},
}
```

- `session_stream.py` 只做最小 SSE 输出

- [ ] **Step 6: 运行 gateway 测试**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway-service-python/tests/test_app.py gateway-service-python/tests/test_session_stream.py -q
```

Expected:

- PASS

### Task 10: 全量回归与文档对齐验证

**Files:**
- Modify: `docs/superpowers/specs/2026-06-13-agent-service-gateway-design.md`（仅当实现中发现命名与 spec 不一致时）
- Test: `tests/test_agent_run_create.py`
- Test: `tests/test_agent_run_input.py`
- Test: `tests/test_delegate_tool.py`
- Test: `tests/test_delegate_chain_internal_code_tool.py`
- Test: `tests/test_delegate_chain_internal_bash_tool.py`
- Test: `tests/test_source_workspace_repository.py`
- Test: `tests/test_session_workspace_repository.py`
- Test: `tests/test_session_repository.py`
- Test: `tests/test_domain_event_repository.py`
- Test: `tests/test_source_workspace_service.py`
- Test: `tests/test_session_workspace_service.py`
- Test: `tests/test_session_service.py`
- Test: `tests/test_session_api.py`
- Test: `gateway-service-python/tests/test_app.py`
- Test: `gateway-service-python/tests/test_session_stream.py`

- [ ] **Step 1: 运行 agent_service 相关测试集合**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest tests/test_sqlite_bootstrap.py tests/test_bootstrap.py tests/test_agent_run_create.py tests/test_agent_run_input.py tests/test_delegate_tool.py tests/test_delegate_chain_internal_code_tool.py tests/test_delegate_chain_internal_bash_tool.py tests/test_source_workspace_repository.py tests/test_session_workspace_repository.py tests/test_session_repository.py tests/test_domain_event_repository.py tests/test_source_workspace_service.py tests/test_session_workspace_service.py tests/test_session_service.py tests/test_session_api.py -q
```

Expected:

- PASS

- [ ] **Step 2: 运行 gateway_service 测试集合**

Run:

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway-service-python/tests/test_app.py gateway-service-python/tests/test_session_stream.py -q
```

Expected:

- PASS

- [ ] **Step 3: 手动核对 spec 与实现命名是否一致**

检查以下命名是否统一：

- `source_workspace`
- `session_workspace`
- `session`
- `domain_event`
- `agent_service`
- `gateway_service`

若发现不一致，直接同步修正文档，不新增新术语。

- [ ] **Step 4: 整轮完成后再做一次总提交**

```powershell
git status --short
git diff -- docs/superpowers/specs/2026-06-13-agent-service-gateway-design.md docs/superpowers/plans/2026-06-13-agent-service-gateway-implementation.md
git diff -- app tests gateway-service-python
```

说明：

- 本计划遵守用户偏好，此处只做最终一次总提交
- 不做中间 commit

## 自检结果

### Spec 覆盖

- `SQLite` 替代 `InMemoryStore`：由 Task 1 和 Task 2 覆盖
- `source workspace / session workspace / session / domain event`：由 Task 3 和 Task 5 覆盖
- `agent_run` / `subtask` 挂接到 `session`：由 Task 4 和 Task 8 覆盖
- `session` API 与生命周期最小闭环：由 Task 5 和 Task 7 覆盖
- `gateway_service` 最小骨架与 SSE：由 Task 9 覆盖
- 全量验证与文档对齐：由 Task 10 覆盖

### Placeholder 扫描

- 已避免使用 `TODO`、`TBD`、`以后实现` 之类占位词
- 每个 task 都给出了具体文件、测试和命令
- 对新增模型和 service 给出了最小代码骨架

### 类型一致性

- 统一使用 `source_workspace_id`
- 统一使用 `session_workspace_id`
- 统一使用 `session_id`
- `domain_event` 的最小事件集与 spec 保持一致
