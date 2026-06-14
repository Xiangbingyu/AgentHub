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

- [x] **Step 1: 写失败测试 —— `SessionRepository.list_all` 与 `SubtaskRepository.list_by_session_id`、`DomainEventRepository.list_by_session_id_since`**

> 已核对：`SubtaskModel` 已含 `session_id: UUID | None` 字段，`list_by_session_id` 直接按字段过滤即可，无需经 run 关联。
> 已核对：本仓库 repository 测试无 conftest / tmp_path，靠唯一 uuid 隔离 + 共享 db；测试沿用此约定（`get_settings` 是 `lru_cache`，monkeypatch env 不生效）。
> 失败测试已写入 `test_subtask_repository_list_by_session.py`（新增）、`test_session_repository.py`、`test_domain_event_repository.py`（各追加一条）。

- [x] **Step 2: 运行确认失败** —— 确认为 `AttributeError: ... has no attribute 'list_by_session_id'`（方法不存在），符合预期。

- [x] **Step 3: 实现三个方法** —— `SessionRepository.list_all`、`DomainEventRepository.list_by_session_id_since(session_id, since=0)`、`SubtaskRepository.list_by_session_id`。

- [x] **Step 4: 运行确认通过** —— 7 passed；改动文件 `ruff check` 全绿。

### Task 2: workspace 文件树包装

**Files:**
- Create: `agent_service/app/runtime/workspace/workspace_tree.py`
- Test: `agent_service/tests/test_workspace_tree.py`

- [x] **Step 1: 写失败测试 —— 给定 `root_path` 与相对 `path`，返回该层 `{type, name, path}` 列表，并验证越界路径被拒**

> 已写入 `test_workspace_tree.py`：根层列举、子目录列举（验证 `path` 为 `src/a.py`）、越界 `../..` 抛 `ValueError`。

- [x] **Step 2: 运行确认失败** —— `ModuleNotFoundError: ...workspace_tree`，符合预期。

- [x] **Step 3: 实现 `list_tree_level`** —— 复用 `WorkspaceSession.resolve_path` 越界保护 + `workspace_root`，单层列举，每项 `{type, name, path(POSIX 相对路径)}`。

- [x] **Step 4: 运行确认通过** —— 3 passed；ruff 全绿。

### Task 3: DomainEventEmitter 与执行链路事件补齐（关键）

**Files:**
- Create: `agent_service/app/services/domain_event_emitter.py`
- Modify: `agent_service/app/services/agent_run_input_service.py`
- Test: `agent_service/tests/test_domain_event_emitter.py`

- [x] **Step 1: 写失败测试 —— emitter 自动计算 `sequence_no` 并落事件**

> 已写入 `test_domain_event_emitter.py`：连续 emit 两条，断言 sequence_no 为 [1,2]、首条 `run.started`、次条 payload `status` 为 completed。setup 用 `bootstrap_memory_store()` 建表。

- [x] **Step 2: 运行确认失败** —— `ModuleNotFoundError: ...domain_event_emitter`，符合预期。

- [x] **Step 3: 实现 `DomainEventEmitter`** —— 包装 `next_sequence_no` + `create`，集中分配 `event_id`/`sequence_no`，支持 `run_id`/`subtask_id` 可选。

- [x] **Step 4: 在 `AgentRunInputService.input` 接入 emit 点** —— 已读 `agent_run_input_service.py` 定位三点：
>   - `run.started`：`_prepare_run_status` 之后、LLM 执行前
>   - `session.message.appended`（agent 回复，`role: assistant`）：worker 路径 `_persist_worker_success` 后；orchestrator 路径 tool loop 之后
>   - `run.completed`：worker 终态、orchestrator `loop_result.next_status`、以及 LLM 异常路径（status="failed"）
>   - 用 `getattr(llm_response, "content")` 取回复，空内容跳过；`session_id is None` 时全部跳过。
>   - 构造函数引入 `DomainEventEmitter(self.domain_event_repository)`。
>   - 新增 `test_agent_run_input_emits_run_lifecycle_events` 验证 run.started / agent 回复 / run.completed 三类事件齐全且 sequence_no 单调。

- [x] **Step 5: 跑现有相关测试确认未回归** —— 全量 agent_service `106 passed`；新增代码 ruff 干净（`agent_run_input_service.py` 既有 8 处 E501 与本次改动无关，未触碰）。

### Task 4: agent_service 读 API router

**Files:**
- Create: `agent_service/app/api/session_read.py`
- Create: `agent_service/app/api/workspace_read.py`
- Create: `agent_service/app/api/agent_run_read.py`
- Modify: `agent_service/app/main.py`
- Test: `agent_service/tests/test_session_read_api.py`
- Test: `agent_service/tests/test_workspace_read_api.py`
- Test: `agent_service/tests/test_agent_run_read_api.py`

- [x] **Step 1: 写失败测试 —— 用 `TestClient` 覆盖核心读接口**

至少覆盖：
- `GET /sessions` → 200，返回列表
- `GET /sessions/{id}` → 200/404
- `GET /sessions/{id}/events?since=N` → 只返回 `sequence_no > N`（**gateway 轮询的核心**）
- `GET /sessions/{id}/subtasks` → 列表
- `GET /source-workspaces`、`/source-workspaces/{id}`、`/source-workspaces/{id}/session-workspaces`、`/session-workspaces/{id}`
- `GET /source-workspaces/{id}/tree?path=` → 文件树层
- `GET /agent-runs/{id}` → 状态/snapshot/plan

> 已写入 `test_session_read_api.py`（4 例）、`test_workspace_read_api.py`（3 例）、`test_agent_run_read_api.py`（1 例）。

- [x] **Step 2: 运行确认失败** —— 8 failed（路由不存在，返回 404），符合预期。

- [x] **Step 3: 实现三个 router 并在 `main.py` 挂载** —— `session_read.py`（同 `/sessions` prefix 加 GET，与既有 POST router 共存）、`workspace_read.py`（source/session-workspace 列表/详情/tree，tree 从 `root_path` 解析并复用 `list_tree_level`，越界返回 400，缺失返回 404）、`agent_run_read.py`（`GET /agent-runs/{id}`，404）。`events` 接口 `since` 为 query 缺省 0 且 `ge=0`。

- [x] **Step 4: 运行确认通过** —— 8 passed；既有写路由（session/agent-run POST）未回归；新增文件 ruff 全绿（auto-fix import 排序 + 手修一处 E501）。

### Task 5: gateway AgentServiceClient 接真实 httpx

**Files:**
- Modify: `gateway_service/app/client/agent_service_client.py`
- Test: `gateway_service/tests/test_agent_service_client.py`

- [x] **Step 1: 写失败测试 —— 用 mock transport / `respx` 或 monkeypatch httpx 验证 URL 与 since 透传**

> 已写入 `test_agent_service_client.py`：monkeypatch `AgentServiceClient._client` 工厂为 `_FakeClient`，捕获 method/url/params/json。覆盖 `list_session_events`(since 透传)、`get_workspace_tree`(path 透传)、`post_message`(写代理 body 透传)、默认 base_url 来自 settings。

- [x] **Step 2: 运行确认失败** —— `AttributeError: ...has no attribute 'base_url'`，符合预期。

- [x] **Step 3: 实现真实 httpx client** —— 构造可注入 `base_url`/`timeout`；`_client()` 工厂返回 `httpx.Client(base_url=, timeout=)`，`_get`/`_post` 统一 `raise_for_status`。读方法：events/sessions/session/subtasks/source-workspaces/session-workspaces/tree/agent-run；写代理：post_message/create_session/delete_session/create_source_workspace/create_session_workspace/create_agent_run。
>   - **签名变更**：`list_session_events(session_id, since=0)`（原 `after_sequence_no`）。旧 stream 仍以无参调用，默认 0 不破坏；Task 6 重写 stream 时显式传 since。
>   - **依赖调整**：`httpx` 从 dev group 提升到主 `dependencies`（运行时需要），`uv sync` 通过。

- [x] **Step 4: 运行确认通过** —— client 4 例 + 旧 stream/app 测试共 7 passed；ruff 全绿。

### Task 6: gateway SSE 轮询流（修正序列化 + Last-Event-ID + 自适应间隔）

**Files:**
- Modify: `gateway_service/app/api/session_stream.py`
- Test: `gateway_service/tests/test_session_stream.py`

- [x] **Step 1: 写失败测试 —— 验证 SSE 帧用 JSON 序列化、`id:` 为 sequence_no、读取 `Last-Event-ID`**

> 已重写 `test_session_stream.py`：`_fast_polling` 把 `STREAM_ACTIVE_INTERVAL`/`STREAM_IDLE_INTERVAL` 置 0、`STREAM_MAX_IDLE_POLLS` 置 2 保证快速确定终止。验证 `data:` 为合法 JSON（含中文 `ensure_ascii=False` 不乱码）、`id: 5`、`event:` 类型；以及 `Last-Event-ID: 7` → client 收到 `since=7`。

- [x] **Step 2: 运行确认失败** —— `AttributeError: ...STREAM_ACTIVE_INTERVAL`，符合预期。

- [x] **Step 3: 改为轮询型异步生成器** —— `last_seq` 从 `last-event-id` 头解析（缺省 0）；`json.dumps(payload, ensure_ascii=False)` 修正原 f-string repr；`id:` 用 `sequence_no`；自适应间隔（有事件 0.3s、空轮 2.0s）；`request.is_disconnected()` 断开即退出；`STREAM_MAX_IDLE_POLLS` 上限收尾避免无限挂起（浏览器自动重连续传）；捕获 `asyncio.CancelledError`。

- [x] **Step 4: 运行确认通过** —— 全量 gateway `8 passed`；ruff 全绿。

### Task 7: gateway 页面聚合 + 写代理 + CORS

**Files:**
- Modify: `gateway_service/app/api/session_page.py`
- Modify: `gateway_service/app/api/workspace_page.py`
- Create: `gateway_service/app/api/write_proxy.py`
- Modify: `gateway_service/app/main.py`
- Test: `gateway_service/tests/test_session_page.py`、`test_workspace_page.py`、`test_write_proxy.py`

- [x] **Step 1: 写失败测试**

- `GET /session-page/{id}`：返回 session 详情 + 历史事件按 `event_scope` 投影成 `main_timeline`/`subtask_thread`/`workspace_panel` 三块 + 绑定 session_workspace 快照
- `GET /workspace-page/{id}`：返回 source 详情 + session_workspaces + tree 根层
- `POST /sessions/{id}/messages`：透传到 agent_service 并回传结果（mock client 验证转发）

> 已写入 `test_page_aggregation.py`（session-page 三块投影 + workspace-page 聚合）、`test_write_proxy.py`（post_message 透传 `/agent-runs/{id}/input`、create_session 透传、CORS 预检头）。
> 注：写消息接口按 agent_service 实际为 `POST /agent-runs/{run_id}/input`（非 `/sessions/{id}/messages`），write_proxy 透传到此。

- [x] **Step 2: 运行确认失败** —— 5 failed（page 投影缺失 / 写代理路由 404 / 无 CORS），符合预期。

- [x] **Step 3: 实现聚合 + 写代理 + CORS**

- `session_page`：调 `get_session` + `list_session_events` 按 `event_scope` 投影到三块，再按 `session_workspace_id` 拉快照。
- `workspace_page`：调 `get_source_workspace` + `list_session_workspaces` + `get_workspace_tree(path=".")`。
- `write_proxy.py`：`POST /agent-runs/{id}/input`、`/agent-runs`、`/sessions`、`/sessions/{id}/delete`、`/source-workspaces`、`/session-workspaces` 透传。
- `main.py` 挂载 `write_proxy` 并加 `CORSMiddleware`；新增 `cors_allow_origins` 配置（缺省 `http://localhost:5173`）。

- [x] **Step 4: 运行确认通过** —— 全量 gateway `13 passed`；ruff 全绿。

### Task 7.5: 后端补 session 发消息接口（实现中追加）

> **背景**：原 spec 写消息为 `POST /sessions/{id}/messages`，但 agent_service 输入接口实为 `POST /agent-runs/{run_id}/input`（按 run）。前端只持有 `session_id`，经用户确认采用「后端补 session 发消息接口」方案：内部解析/创建该 session 的活动 orchestrator run 再转 input。

- [x] **Step 1: repository 补方法 + service TDD** —— `AgentRunRepository.list_by_session_id`、`AgentRepository.list_all`；`SessionMessageService(input_service 可注入)` 解析活动 orchestrator run（无则用 `AgentRunCreateService` 新建，workspace_id 取 `session.session_workspace_id`）再转 `input`。`test_session_message_service.py` 4 例（新建 run / 复用 run / 未知 session 抛错 / orchestrator 已 seed）。
- [x] **Step 2: agent_service API** —— `POST /sessions/{session_id}/messages`（body `{content}`），未知 session 返回 404。`test_session_message_api.py` 2 例，monkeypatch `_resolve_input_service` 避免打真实 LLM。
- [x] **Step 3: gateway 透传** —— `AgentServiceClient.post_session_message` + write_proxy `POST /sessions/{id}/messages`。`test_write_proxy.py` 追加 1 例。
- [x] **Step 4: 验证** —— agent_service 消息相关 7 passed、gateway 14 passed；ruff 全绿。前端发消息调 gateway `POST /sessions/{id}/messages`，只需 session_id。

### Task 8: 前端接入真实接口与 SSE

**Files:**
- Create: `frontend/src/utils/api.js`
- Create: `frontend/src/hooks/useSessionStream.js`
- Modify: `frontend/vite.config.js`（新增 `/api` → gateway:8080 代理）
- Modify: `frontend/src/pages/Chat/Chat.jsx`
- Modify: `frontend/src/pages/Workspace/Workspace.jsx`
- Modify: `frontend/src/components/ChatPanel/ChatPanel.jsx`（启用发送 + 受控输入）
- Modify: `frontend/src/components/WorkspaceBrowser/WorkspaceBrowser.jsx`（`onExpandDirectory` 懒加载回调）
- Delete: `frontend/src/data/mockChat.js` / `mockWorkspace.js`（已被真实接口取代）
- 追加: gateway `read_proxy.py`（`GET /sessions`、`/source-workspaces`、`/source-workspaces/{id}/tree`），让前端只跟 gateway 对话。

- [x] **Step 1: `utils/api.js`** —— `fetchJson` 封装，统一走同源 `/api`（Vite 代理到 gateway:8080）；导出 listSessions/getSessionPage/listSourceWorkspaces/getWorkspacePage/getWorkspaceTree/postSessionMessage/createSession/sessionStreamUrl。

- [x] **Step 2: `hooks/useSessionStream.js`** —— 封装 `EventSource`，监听已知 event 类型；切换 sessionId 关旧开新；解析 `data:` JSON、`lastEventId` 作 sequence_no；依赖浏览器原生 `Last-Event-ID` 重连。

- [x] **Step 3: Chat 页接入** —— 启动拉 `listSessions`；选中 session 拉 `getSessionPage` 取历史（过滤 `session.message.appended` 投影成消息）+ 开 `useSessionStream`；发消息 `postSessionMessage`（只需 session_id），用户消息与 agent 回复均经 SSE 回流、按 `sequence_no` 去重排序追加；RuntimePanel 由 session + workspace 快照派生。

- [x] **Step 4: Workspace 页接入** —— 启动拉 `listSourceWorkspaces`，逐 source 拉 `getWorkspacePage` 取根层 tree + session_workspaces；目录展开经 `onExpandDirectory` 调 `getWorkspaceTree(path)` 懒加载并不可变注入 children；选中节点构造最小详情。

- [x] **Step 5: 前端构建校验** —— `npm run build` 通过；`npm run lint` 0 error（修了 no-useless-assignment ×2、set-state-in-effect ×1：空 session 早返回不再同步 setState）。

### Task 9: 端到端验证与单次总提交

- [x] **Step 1: 全量后端测试**

```powershell
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m pytest
& "E:\Github\AgentHub-weon\backend-python\.venv\Scripts\python.exe" -m ruff check .
```

实测：`pytest` **137 passed**（含真实 LLM e2e，约 6m45s）。`ruff check .` 全库 234 个预存错误（E501/I001/F401，遍布未改文件）；仅对本轮改/新建文件单测，经 `git stash` 比对确认 `agent_run_input_service.py`/`test_agent_run_input.py` 的 7×E501 + 2×I001 **改动前即存在**，本轮**零新增**违规，符合最小改动纪律。

- [x] **Step 2: 手动端到端冒烟**

起 agent_service(:8000) + gateway(:8080)，构造真实 source/session_workspace/session 链路后冒烟：

- ✅ gateway 读路径与 agent_service 直连一致（`/sessions`、`/source-workspaces`、`read_proxy`）
- ✅ `workspace-page` 读到真实文件树，`/tree?path=pkg` 逐层懒加载正常
- ✅ 发消息 `POST /sessions/{id}/messages` → orchestrator run → **真实 LLM 回复经 SSE 回流**；SSE 帧 `id:1..5`（session_created → user message → run.started → assistant reply → run.completed）均为合法 JSON，`id:` = sequence_no，`since`/Last-Event-ID 续传正常
- ✅ **修复冒烟暴露的 2 处真实 bug**：`session_page`/`workspace_page` 聚合在 session_workspace 缺失（404）或 root_path 不存在（400/404）时会整页 500——改为捕获并优雅降级（`session_workspace=None` / 空树），补 2 个降级测试（gateway 19 passed）
- ✅ 将运行时产物目录 `.AgentHub/` 与 `.env` 加入 `backend-python/.gitignore`，避免误入库

- [x] **Step 3: 单次总提交**（仅在以上全部通过后）

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
