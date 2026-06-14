# 前端接入与实时反馈 Implementation Plan（Gateway 接入层）

> **For agentic workers:** REQUIRED SUB-SKILL: 使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现本计划。每步用 checkbox（`- [ ]`）跟踪，遵循「先写失败测试 → 确认失败 → 实现 → 确认通过」的 TDD 节奏。

**Goal:** 把当前仅为桩实现的 `gateway_service` 接成真实可用的前端适配层，并为 `agent_service` 补齐前端所需的最小读接口与 `domain_event` 产出，最终打通「前端发消息 → agent_service 执行并落事件 → gateway SSE 轮询回流 → 前端实时渲染」这条端到端链路。

**Architecture:** 严格遵循 `docs/superpowers/specs/2026-06-14-frontend-gateway-integration-design.md` 的设计结论：`agent_service` 只输出领域事实（带 `sequence_no` 的 `domain_events`），不感知前端连接；`gateway_service` 只做聚合查询、SSE 投影与连接管理；实时传输采用「HTTP 写 + SSE 读」，gateway 轮询 agent_service 的 events 接口 tail 事件流；本轮不拆第三个服务、不引入 MQ、不改 run 同步执行模型、不实现 session_workspace 派生。

**Tech Stack:** Python 3.11, FastAPI, Pydantic, sqlite3, httpx, pytest；前端 React 19 + Vite，`EventSource` + `fetch`。

---

## 约束与执行说明

- **不做分步 commit**，只在整轮实现与验证全部通过后做一次总提交（沿用用户既定偏好）。
- 复用现有 `AgentRunInputService`、`RuntimeAssembler`、`LoopEngine`、`delegate_tool`、`workspace_session`、各 repository 与 `get_connection` 模式，不推翻主链路。
- 导入一律用服务包根的绝对路径：`from agent_service.app... import ...`、`from gateway_service.app... import ...`。
- 模型变更走 `model_copy(update={...})`，repository 用 `INSERT OR REPLACE` 全文写。
- run 仍同步执行：事件在 `POST /input` 返回时一次性落库，gateway 轮询拉取。**本轮不做 run 异步化、不做进程内 pub-sub/queue。**
- 端口约定：`agent_service` :8000、`gateway_service` :8080、前端 dev :5173。
- 所有后端验证命令使用虚拟环境 Python：

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest ...
```

- 测试运行目录为 `backend-python/`（`pythonpath = ["."]`）。前端命令在 `frontend/` 下用 `npm`。

## 现状基线（实现前，已核对代码）

- `gateway_service` 全部为桩：`AgentServiceClient.list_session_events` 直接 `return []`；`session_stream.py` 的 `data:` 用 f-string 输出 Python repr；`session_page`/`workspace_page` 返回硬编码空结构；无 CORS。
- `agent_service` 只有 5 个 POST，无任何 GET/list/stream 接口。
- `DomainEventRepository`：`list_by_session_id`（全表扫 + 按 `sequence_no` 排序）、`next_sequence_no` 已具备；**无 `since` 过滤**。
- `SessionRepository` 缺 `list_all`；`SubtaskRepository` 有 `list_by_parent_run_id`，缺 `list_by_session_id`。
- 当前只落两类事件：用户消息 `session.message.appended` 与 session 创建标记；**agent 回复未落事件**，结果存于 `agent_run.context_snapshot`。
- `WorkspaceSession.list_dir` 只列单层；真实工作目录当前取自 `TEST_WORKSPACE_PATH`，未读 `source_workspace.root_path`。

## 文件结构映射

### agent_service 改动

- Modify: `agent_service/app/repositories/session_repository.py`（加 `list_all`）
- Modify: `agent_service/app/repositories/subtask_repository.py`（加 `list_by_session_id`）
- Modify: `agent_service/app/repositories/domain_event_repository.py`（加 `list_by_session_id_since`）
- Create: `agent_service/app/services/domain_event_emitter.py`
- Modify: `agent_service/app/services/agent_run_input_service.py`（emit run.started / agent 回复 / run.completed）
- Create: `agent_service/app/api/session_read.py`
- Create: `agent_service/app/api/workspace_read.py`
- Create: `agent_service/app/api/agent_run_read.py`
- Create: `agent_service/app/runtime/workspace/workspace_tree.py`（递归/单层 tree 包装）
- Modify: `agent_service/app/main.py`（挂载新 router）

### gateway_service 改动

- Modify: `gateway_service/app/client/agent_service_client.py`（接真实 httpx）
- Modify: `gateway_service/app/api/session_stream.py`（轮询型 SSE + JSON 序列化 + Last-Event-ID）
- Modify: `gateway_service/app/api/session_page.py`（聚合 session 详情 + 投影历史事件）
- Modify: `gateway_service/app/api/workspace_page.py`（聚合 source + session_workspaces + tree 根层）
- Create: `gateway_service/app/api/write_proxy.py`（写代理透传）
- Modify: `gateway_service/app/main.py`（挂载 write_proxy + CORSMiddleware）

### 前端改动

- Create: `frontend/src/utils/api.js`
- Create: `frontend/src/hooks/useSessionStream.js`
- Modify: `frontend/src/data/mockChat.js` / `mockWorkspace.js`（替换为真实接口或保留作 fallback）
- Modify: `frontend/src/pages/Chat/Chat.jsx`
- Modify: `frontend/src/pages/Workspace/Workspace.jsx`

### 测试文件

- Create: `agent_service/tests/test_session_read_api.py`
- Create: `agent_service/tests/test_workspace_read_api.py`
- Create: `agent_service/tests/test_agent_run_read_api.py`
- Create: `agent_service/tests/test_domain_event_emitter.py`
- Modify: `agent_service/tests/test_session_repository.py`（如存在）
- Create: `agent_service/tests/test_subtask_repository_list_by_session.py`
- Create: `agent_service/tests/test_workspace_tree.py`
- Create: `gateway_service/tests/test_agent_service_client.py`
- Modify: `gateway_service/tests/test_session_stream.py`
- Create: `gateway_service/tests/test_write_proxy.py`
- Modify: `gateway_service/tests/test_session_page.py` / `test_workspace_page.py`（如存在）

---

## 实施拆分

按依赖顺序推进：先打通 agent_service 读路径与事件产出（Task 1–4），再接 gateway（Task 5–7），最后接前端并端到端验证（Task 8–9）。每个 Task 内严格 TDD。

### Task 1: agent_service repository 补齐读方法

**Files:**
- Modify: `agent_service/app/repositories/session_repository.py`
- Modify: `agent_service/app/repositories/subtask_repository.py`
- Modify: `agent_service/app/repositories/domain_event_repository.py`
- Test: `agent_service/tests/test_subtask_repository_list_by_session.py`

- [ ] **Step 1: 写失败测试 —— `SessionRepository.list_all` 与 `SubtaskRepository.list_by_session_id`、`DomainEventRepository.list_by_session_id_since`**

```python
from uuid import uuid4

from agent_service.app.database.bootstrap import bootstrap_database
from agent_service.app.models.subtask import SubtaskModel
from agent_service.app.repositories.subtask_repository import SubtaskRepository


def test_list_by_session_id_returns_only_matching(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "t.db"))
    bootstrap_database()
    repo = SubtaskRepository()
    sid = uuid4()
    # 构造两条 subtask，一条属于 sid，一条不属于（按 SubtaskModel 实际字段填充）
    # 断言 repo.list_by_session_id(sid) 只返回属于 sid 的那条
    ...
```

> 注意：`SubtaskModel` 是否已有 `session_id` 字段需先核对；若无，则 `list_by_session_id` 改为经 `parent_run_id → run.session_id` 关联，或在 emit 时记 `session_id`。先读模型再定方案。

- [ ] **Step 2: 运行确认失败**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_subtask_repository_list_by_session.py -v
```

Expected: FAIL，提示方法不存在。

- [ ] **Step 3: 实现三个方法**

`SessionRepository.list_all`：

```python
def list_all(self) -> list[SessionModel]:
    conn = get_connection()
    rows = conn.execute("SELECT payload FROM sessions").fetchall()
    conn.close()
    return [SessionModel.model_validate_json(row[0]) for row in rows]
```

`DomainEventRepository.list_by_session_id_since`（复用现有排序逻辑，应用层过滤 `sequence_no > since`）：

```python
def list_by_session_id_since(self, session_id: UUID, since: int = 0) -> list[DomainEventModel]:
    return [e for e in self.list_by_session_id(session_id) if e.sequence_no > since]
```

`SubtaskRepository.list_by_session_id`：按上一步核对结果实现（直接字段过滤或经 run 关联）。

- [ ] **Step 4: 运行确认通过**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_subtask_repository_list_by_session.py -v
```

Expected: PASS。

### Task 2: workspace 文件树包装

**Files:**
- Create: `agent_service/app/runtime/workspace/workspace_tree.py`
- Test: `agent_service/tests/test_workspace_tree.py`

- [ ] **Step 1: 写失败测试 —— 给定 `root_path` 与相对 `path`，返回该层 `{type, name, path}` 列表，并验证越界路径被拒**

```python
from pathlib import Path

from agent_service.app.runtime.workspace.workspace_tree import list_tree_level


def test_list_tree_level_returns_entries(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x")
    (tmp_path / "readme.md").write_text("y")

    entries = list_tree_level(str(tmp_path), ".")
    names = {e["name"]: e["type"] for e in entries}

    assert names["src"] == "directory"
    assert names["readme.md"] == "file"


def test_list_tree_level_rejects_escape(tmp_path: Path) -> None:
    import pytest
    with pytest.raises(ValueError):
        list_tree_level(str(tmp_path), "../..")
```

- [ ] **Step 2: 运行确认失败**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_workspace_tree.py -v
```

- [ ] **Step 3: 实现 `list_tree_level`**

复用 `WorkspaceSession.resolve_path` 的越界保护（或等价 `Path.resolve()` + 前缀校验），列出单层目录项，每项形如 `{"type": "directory"|"file", "name": str, "path": str}`（`path` 为相对 `root_path` 的 POSIX 路径）。前端 WorkspaceBrowser 按需逐层展开，单层返回即可。

- [ ] **Step 4: 运行确认通过**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_workspace_tree.py -v
```

### Task 3: DomainEventEmitter 与执行链路事件补齐（关键）

**Files:**
- Create: `agent_service/app/services/domain_event_emitter.py`
- Modify: `agent_service/app/services/agent_run_input_service.py`
- Test: `agent_service/tests/test_domain_event_emitter.py`

- [ ] **Step 1: 写失败测试 —— emitter 自动计算 `sequence_no` 并落事件**

```python
from uuid import uuid4

from agent_service.app.database.bootstrap import bootstrap_database
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.services.domain_event_emitter import DomainEventEmitter


def test_emit_assigns_monotonic_sequence(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "t.db"))
    bootstrap_database()
    sid, swid = uuid4(), uuid4()
    emitter = DomainEventEmitter()

    emitter.emit(session_id=sid, session_workspace_id=swid,
                 event_type="run.started", event_scope="main_timeline",
                 payload={"run_id": "r1"})
    emitter.emit(session_id=sid, session_workspace_id=swid,
                 event_type="run.completed", event_scope="main_timeline",
                 payload={"run_id": "r1", "status": "completed"})

    events = DomainEventRepository().list_by_session_id(sid)
    assert [e.sequence_no for e in events] == [1, 2]
    assert events[0].event_type == "run.started"
```

- [ ] **Step 2: 运行确认失败**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_domain_event_emitter.py -v
```

- [ ] **Step 3: 实现 `DomainEventEmitter`**

包装 `next_sequence_no` + `DomainEventRepository.create`，集中处理 `event_id`（`uuid4`）、`sequence_no` 分配，避免散落：

```python
class DomainEventEmitter:
    def __init__(self, repo: DomainEventRepository | None = None) -> None:
        self._repo = repo or DomainEventRepository()

    def emit(self, *, session_id, session_workspace_id, event_type, event_scope,
             payload, run_id=None, subtask_id=None) -> DomainEventModel:
        seq = self._repo.next_sequence_no(session_id)
        event = DomainEventModel(
            event_id=uuid4(), session_id=session_id,
            session_workspace_id=session_workspace_id, run_id=run_id,
            subtask_id=subtask_id, event_type=event_type, event_scope=event_scope,
            payload=payload, sequence_no=seq,
        )
        return self._repo.create(event)
```

- [ ] **Step 4: 在 `AgentRunInputService.input` 接入 emit 点**

先读 `agent_run_input_service.py` 定位执行前/LLM 返回后/终态三个位置，补：
- `run.started`（`main_timeline`，进入执行前，payload 含 `run_id`、`agent_kind`）
- `session.message.appended`（`main_timeline`，agent LLM 回复后，payload 含 `content`、`role: "assistant"`）
- `run.completed`（`main_timeline`，run 终态时，payload 含 `run_id`、`status`）

> `subtask.delegated` / `subtask.completed` / `plan.updated` / `workspace.changed` 列入设计但本轮非必须；若 emit 点改动小可一并补，否则留待下一轮，不阻塞端到端链路。先保证 agent 回复可见。

- [ ] **Step 5: 跑现有相关测试确认未回归**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_domain_event_emitter.py agent_service/tests/test_agent_run_input.py -v
```

Expected: PASS（input 测试若断言事件数量需同步更新）。

### Task 4: agent_service 读 API router

**Files:**
- Create: `agent_service/app/api/session_read.py`
- Create: `agent_service/app/api/workspace_read.py`
- Create: `agent_service/app/api/agent_run_read.py`
- Modify: `agent_service/app/main.py`
- Test: `agent_service/tests/test_session_read_api.py`
- Test: `agent_service/tests/test_workspace_read_api.py`
- Test: `agent_service/tests/test_agent_run_read_api.py`

- [ ] **Step 1: 写失败测试 —— 用 `TestClient` 覆盖核心读接口**

至少覆盖：
- `GET /sessions` → 200，返回列表
- `GET /sessions/{id}` → 200/404
- `GET /sessions/{id}/events?since=N` → 只返回 `sequence_no > N`（**gateway 轮询的核心**）
- `GET /sessions/{id}/subtasks` → 列表
- `GET /source-workspaces`、`/source-workspaces/{id}`、`/source-workspaces/{id}/session-workspaces`、`/session-workspaces/{id}`
- `GET /source-workspaces/{id}/tree?path=` → 文件树层
- `GET /agent-runs/{id}` → 状态/snapshot/plan

```python
from fastapi.testclient import TestClient

from agent_service.app.main import app


def test_get_session_events_since_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "t.db"))
    # bootstrap + 造 session + 造若干 domain_event
    client = TestClient(app)
    resp = client.get(f"/sessions/{sid}/events", params={"since": 1})
    assert resp.status_code == 200
    assert all(e["sequence_no"] > 1 for e in resp.json())
```

- [ ] **Step 2: 运行确认失败**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_session_read_api.py agent_service/tests/test_workspace_read_api.py agent_service/tests/test_agent_run_read_api.py -v
```

- [ ] **Step 3: 实现三个 router 并在 `main.py` 挂载**

各 router 直接调 Task 1 的 repository 方法与 Task 2 的 `list_tree_level`；`events` 接口用 `list_by_session_id_since(session_id, since)`，`since` 为 query 参数缺省 0；tree 接口从 `source_workspace.root_path` 解析根目录再调 `list_tree_level`。返回体用现有 schema 或直接 `model_dump()`。

- [ ] **Step 4: 运行确认通过**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest agent_service/tests/test_session_read_api.py agent_service/tests/test_workspace_read_api.py agent_service/tests/test_agent_run_read_api.py -v
```

### Task 5: gateway AgentServiceClient 接真实 httpx

**Files:**
- Modify: `gateway_service/app/client/agent_service_client.py`
- Test: `gateway_service/tests/test_agent_service_client.py`

- [ ] **Step 1: 写失败测试 —— 用 mock transport / `respx` 或 monkeypatch httpx 验证 URL 与 since 透传**

```python
def test_list_session_events_calls_correct_url(monkeypatch):
    captured = {}
    # monkeypatch httpx.Client.get 捕获 url/params，返回假响应
    client = AgentServiceClient(base_url="http://x:8000")
    client.list_session_events("sid", since=3)
    assert captured["url"].endswith("/sessions/sid/events")
    assert captured["params"]["since"] == 3
```

- [ ] **Step 2: 运行确认失败**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway_service/tests/test_agent_service_client.py -v
```

- [ ] **Step 3: 实现真实 httpx client**

从 `get_settings().agent_service_base_url` 取 base（构造可注入 `base_url` 便于测试）。方法：`list_session_events(session_id, since)`、`get_session`/`list_sessions`、`get_source_workspace`/`list_source_workspaces`、`list_session_workspaces`/`get_session_workspace`、`get_workspace_tree(source_id, path)`、`get_agent_run`、`list_subtasks`，写代理 `create_session`/`post_message`/`create_source_workspace`/`create_session_workspace`/`delete_session`。统一 `httpx.Client(base_url=..., timeout=...)`，对非 2xx 抛出。

> **注意**：`list_session_events` 原桩参数名为 `after_sequence_no`，新接口用 `since`；统一改为 `since` 并同步更新 `session_stream.py` 调用处。

- [ ] **Step 4: 运行确认通过**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway_service/tests/test_agent_service_client.py -v
```

### Task 6: gateway SSE 轮询流（修正序列化 + Last-Event-ID + 自适应间隔）

**Files:**
- Modify: `gateway_service/app/api/session_stream.py`
- Test: `gateway_service/tests/test_session_stream.py`

- [ ] **Step 1: 写失败测试 —— 验证 SSE 帧用 JSON 序列化、`id:` 为 sequence_no、读取 `Last-Event-ID`**

```python
def test_stream_emits_json_data_and_seq_id(monkeypatch):
    # mock AgentServiceClient.list_session_events 返回一条事件后置空
    # 用 TestClient stream，断言 data: 行是合法 JSON、id: 行是 sequence_no
    ...
```

> 轮询循环需可终止：测试里让 client 返回一批后即空，并对循环加最大轮次或注入「连接断开」信号，避免测试挂死。实现用 `asyncio.sleep` 让出，捕获 `asyncio.CancelledError` 退出。

- [ ] **Step 2: 运行确认失败**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway_service/tests/test_session_stream.py -v
```

- [ ] **Step 3: 改为轮询型异步生成器**

```python
@router.get("/{session_id}/stream")
async def session_stream(session_id: str, request: Request):
    client = AgentServiceClient()
    last_seq = int(request.headers.get("last-event-id", 0) or 0)

    async def iterator():
        idle = 0
        try:
            while not await request.is_disconnected():
                events = client.list_session_events(session_id, since=last_seq)
                if events:
                    idle = 0
                    for e in events:
                        nonlocal_seq = e["sequence_no"]
                        yield (
                            f"id: {nonlocal_seq}\n"
                            f"event: {e['event_type']}\n"
                            f"data: {json.dumps(e['payload'], ensure_ascii=False)}\n\n"
                        )
                    # 更新 last_seq 到最后一条
                else:
                    idle += 1
                interval = 0.3 if events else min(2.0, 0.3 * (idle + 1))
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return

    return StreamingResponse(iterator(), media_type="text/event-stream")
```

关键点：`data:` 用 `json.dumps`（修正原 f-string repr）；`id:` 用 `sequence_no` 支撑 `Last-Event-ID` 续传；自适应间隔（有新事件 300ms，连续空轮退避到 2s）；`last_seq` 闭包变量随每条事件推进。

- [ ] **Step 4: 运行确认通过**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway_service/tests/test_session_stream.py -v
```

### Task 7: gateway 页面聚合 + 写代理 + CORS

**Files:**
- Modify: `gateway_service/app/api/session_page.py`
- Modify: `gateway_service/app/api/workspace_page.py`
- Create: `gateway_service/app/api/write_proxy.py`
- Modify: `gateway_service/app/main.py`
- Test: `gateway_service/tests/test_session_page.py`、`test_workspace_page.py`、`test_write_proxy.py`

- [ ] **Step 1: 写失败测试**

- `GET /session-page/{id}`：返回 session 详情 + 历史事件按 `event_scope` 投影成 `main_timeline`/`subtask_thread`/`workspace_panel` 三块 + 绑定 session_workspace 快照
- `GET /workspace-page/{id}`：返回 source 详情 + session_workspaces + tree 根层
- `POST /sessions/{id}/messages`：透传到 agent_service 并回传结果（mock client 验证转发）

- [ ] **Step 2: 运行确认失败**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway_service/tests/test_session_page.py gateway_service/tests/test_workspace_page.py gateway_service/tests/test_write_proxy.py -v
```

- [ ] **Step 3: 实现聚合 + 写代理 + CORS**

- `session_page` / `workspace_page` 调 client 拉数据，按设计的投影表（`event_scope → 前端块`）做形状转换，不含编排语义。
- `write_proxy.py`：`POST /sessions`、`POST /sessions/{id}/messages`、`POST /source-workspaces`、`POST /session-workspaces`、`POST /sessions/{id}/delete` 透传到对应 agent_service 接口。
- `main.py` 挂载 `write_proxy` router，并加 `CORSMiddleware`，允许来源 `http://localhost:5173`（dev）。

- [ ] **Step 4: 运行确认通过**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest gateway_service/tests/ -v
```

### Task 8: 前端接入真实接口与 SSE

**Files:**
- Create: `frontend/src/utils/api.js`
- Create: `frontend/src/hooks/useSessionStream.js`
- Modify: `frontend/src/pages/Chat/Chat.jsx`
- Modify: `frontend/src/pages/Workspace/Workspace.jsx`
- Modify: `frontend/src/data/mockChat.js` / `mockWorkspace.js`

- [ ] **Step 1: `utils/api.js`** —— `fetchJson` 封装，base URL 指向 gateway（`http://localhost:8080`，建议走 Vite proxy 或 env 变量），统一错误处理。

- [ ] **Step 2: `hooks/useSessionStream.js`** —— 封装 `EventSource('/api/sessions/{id}/stream')`：按 `event:` 类型分发到 `main_timeline`/`subtask_thread`/`workspace_panel` 回调；按 `sequence_no` 去重与排序；切换 session 时关旧开新；依赖浏览器原生 `Last-Event-ID` 重连。

- [ ] **Step 3: Chat 页接入** —— 选中 session：`GET /session-page/{id}` 拉历史 + 开 `useSessionStream`；发消息：`POST /api/sessions/{id}/messages`，agent 回复经 SSE 回流追加。

- [ ] **Step 4: Workspace 页接入** —— `GET /workspace-page/{id}` 一次加载，文件树按需调 `tree` 接口逐层展开；RuntimePanel 消费 `workspace_panel` / run 状态事件。

- [ ] **Step 5: 前端构建校验**

```bash
cd frontend && npm run build && npm run lint
```

Expected: 构建通过、lint 无错（注意 React 19 JSX transform 不需 `import React`，避免未用导入报错）。

### Task 9: 端到端验证与单次总提交

- [ ] **Step 1: 全量后端测试**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m ruff check .
```

- [ ] **Step 2: 手动端到端冒烟**

分别起 agent_service(:8000)、gateway_service(:8080)、前端(:5173)：

```bash
cd backend-python
uv run fastapi dev agent_service/app/main.py
uv run fastapi dev gateway_service/app/main.py   # 另一终端
```

- 用 `curl -N http://localhost:8080/api/sessions/{id}/stream` 验证 SSE 帧为合法 JSON、`id:` 为 sequence_no
- 前端发一条消息，确认 agent 回复经 SSE 回流并渲染到 Chat
- Workspace 页能拉到 source/session_workspaces 与逐层文件树

- [ ] **Step 3: 单次总提交**（仅在以上全部通过后）

```bash
git add -A
git commit
```

提交信息覆盖：agent_service 读接口 + domain_event 产出、gateway 真实 client + 轮询 SSE + 聚合 + 写代理 + CORS、前端接入 SSE 与真实接口。**全程不做分步 commit。**

---

## 自检结果

- **是否遵循设计 spec**：是。链路、连接粒度、gateway 轮询、事件投影、非目标均对齐 `2026-06-14-frontend-gateway-integration-design.md`。
- **是否最小改动**：是。不改 run 同步执行、不拆服务、不引 MQ/queue、不实现 session_workspace 派生。
- **关键风险**：
  1. `SubtaskModel` 是否含 `session_id` —— Task 1 Step 1 已要求先核对，决定 `list_by_session_id` 实现方式。
  2. SSE 轮询测试易挂死 —— Task 6 已要求注入终止信号/最大轮次。
  3. `list_session_events` 参数名从 `after_sequence_no` 改 `since` —— Task 5 已标注需同步 stream 调用处。
  4. agent 回复 emit 点定位 —— Task 3 Step 4 要求先读 `agent_run_input_service.py` 再下手，不臆测行号。
- **验证可独立性**：每个 Task 均有独立 pytest 命令，agent_service 读接口可 `curl`，gateway SSE 可 `curl -N`，前端最后接。
