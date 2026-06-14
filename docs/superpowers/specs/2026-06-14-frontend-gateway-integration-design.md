# 前端接入与实时反馈实现设计（Gateway 接入层）

## 概述

本设计是 `2026-06-13-agent-service-gateway-design.md` 的「阶段 3」落地方案，目标是把当前仅为桩实现的 `gateway_service` 接成真实可用的前端适配层，并为 `agent_service` 补齐前端所需的最小读接口与事件产出。

本设计严格遵循既有架构结论：

- `agent_service` 只输出领域事实（`domain_events`），不管前端连接
- `gateway_service` 只做聚合查询、实时投影与连接管理
- 实时传输采用 `HTTP 写 + SSE 读`
- 不拆第三个 `workspace_service`，不引入 MQ/事件总线

前端已按 `source_workspace -> session_workspace -> session` 模型完成静态框架（Chat 页、Workspace 页），本设计负责把它接到后端真实数据。

## 现状基线（实现前）

经代码核对，当前实际状态如下：

**gateway_service —— 全部为桩**

- `GET /sessions/{id}/stream`：SSE 骨架存在，但调用的 `AgentServiceClient.list_session_events` 直接 `return []`
- `GET /session-page/{id}`、`GET /workspace-page/{id}`：返回硬编码空结构
- `AgentServiceClient`：无任何 httpx 调用，`agent_service_base_url` 配置存在但无人读取
- 无 CORS，无 WebSocket

**agent_service —— 只有写，没有读**

- 仅 5 个 POST：`/agent-runs`、`/agent-runs/{id}/input`、`/sessions`、`/session-workspaces`、`/source-workspaces`
- 无任何 GET / list / 流式接口
- `POST /agent-runs/{id}/input` 内 LLM 为**同步阻塞**执行，整个 run（含 orchestrator 工具循环）跑完才返回
- `domain_events` 表是唯一事件时间线，具备按 session 单调递增的 `sequence_no`（`next_sequence_no`），`list_by_session_id` 已按 `sequence_no` 排序
- 当前只写入两类事件：`session.message.appended`（用户消息）、session 创建标记。**agent 回复未落事件**，结果存于 `agent_run.context_snapshot["worker_execution"]`
- `source_workspace.root_path` / `session_workspace.root_path` 为裸字符串，创建时不校验；运行时真实工作目录取自 `TEST_WORKSPACE_PATH`，**未读取 root_path**
- `session_workspace` 的「派生」机制（拷贝 / git worktree）尚无任何实现

## 设计决策

| 决策点 | 结论 | 理由 |
|---|---|---|
| 传输层 | HTTP 写 + SSE 读 | 数据流以服务端→前端单向推送为主，用户输入为离散 POST；SSE 有原生重连与 `Last-Event-ID` 续传 |
| 连接粒度 | 按 session 单独开流 | 选中 session 才开 `/sessions/{id}/stream`，切换则关旧开新；映射 SSE 最自然，无需订阅协议 |
| 改造范围 | 最小读路径 | run 仍同步执行，本轮先打通"拉历史 + 拉最终结果"的链路，不改异步执行 |
| gateway 取事件方式 | gateway 轮询 agent_service | 当前 run 同步执行，事件在 input 返回时一次性落库，直推无收益且需在 agent_service 内建 pub-sub，违背最小改动 |
| session_workspace 派生 | 本轮不实现 | 与架构文档非目标一致；第一阶段 root_path 指向真源或手填目录，先通读链路 |

## 链路总览

```
                  HTTP 写 (POST messages/sessions/workspaces)
   ┌─────────┐   ─────────────────────────────────────────►   ┌──────────────┐
   │ 前端     │                                                 │ gateway      │
   │ EchoMind │   ◄─────────────────────────────────────────   │ _service     │
   └─────────┘   SSE 读 (GET /sessions/{id}/stream, id: seq)    └──────┬───────┘
        ▲                                                              │ HTTP
        │ 聚合读 (GET /workspace-page, /session-page, /sessions)        │ (httpx)
        └──────────────────────────────────────────────────────       ▼
                                                              ┌──────────────┐
                                                              │ agent_service│
                                                              │  domain_events│ (SQLite)
                                                              └──────────────┘
```

核心不变量：**所有变化都落成带 `sequence_no` 的 `domain_event`，gateway 通过轮询 tail 这条流并投影成前端 SSE 事件。**

## 前端连接行为（按 session 单独开流）

1. **应用启动**：拉列表，不建任何流
   - `GET /workspace-page` 或 `GET /sessions`（会话列表）
   - 渲染 SessionList / WorkspaceBrowser
2. **选中某 session**：
   - `GET /session-page/{id}` 拉历史时间线与 workspace 快照
   - 打开 `EventSource('/api/sessions/{id}/stream')` 建立 SSE
3. **切换 session**：关闭旧 `EventSource`，对新 session 重复步骤 2
4. **断线**：浏览器 `EventSource` 自动重连，请求头携带 `Last-Event-ID`（上次收到的 `sequence_no`），gateway 据此从该点续传
5. **发消息**：`POST /api/sessions/{id}/messages`（纯写），agent 回复经由已开的 SSE 流回

前端不维护 app 级长连接，连接生命周期与"当前查看的 session"绑定，简单且与后端 `/sessions/{id}/stream` 一一对应。

## agent_service 改动

### 1. 新增读接口（全部接现有 repository）

| 接口 | 方法 | 接到现有代码 | 备注 |
|---|---|---|---|
| `/sessions` | GET | `SessionRepository` 需补 `list_all` | 会话列表 |
| `/sessions/{id}` | GET | `get_by_id` ✅ | 会话详情 |
| `/sessions/{id}/events?since=N` | GET | `DomainEventRepository.list_by_session_id` ✅ | **gateway 轮询的核心接口**，返回 `sequence_no > N` 的事件，已排序 |
| `/sessions/{id}/subtasks` | GET | `SubtaskRepository` 需补 `list_by_session_id` | 子任务流 |
| `/source-workspaces` | GET | `list_all` ✅ | workspace 列表 |
| `/source-workspaces/{id}` | GET | `get_by_id` ✅ | |
| `/source-workspaces/{id}/session-workspaces` | GET | `list_by_source_workspace_id` ✅ | |
| `/session-workspaces/{id}` | GET | `get_by_id` ✅ | |
| `/source-workspaces/{id}/tree?path=` | GET | `WorkspaceSession.list_dir`（需递归包装） | 文件树，读 `root_path` |
| `/agent-runs/{id}` | GET | `get_by_id` ✅ | 状态 / runtime_snapshot / plan |

`since=N` 语义：返回 `sequence_no > N` 的事件；`N` 缺省为 0（全量）。直接复用 `list_by_session_id` 后在应用层过滤即可，无需改存储。

### 2. 补齐 domain_event 产出（关键）

当前 SSE 流里只有用户自己的消息。需在执行链路补写以下事件，否则前端看不到 agent 的任何反馈：

| 事件 | 写入点 | event_scope | payload 要点 |
|---|---|---|---|
| `run.started` | `AgentRunInputService.input` 进入执行前 | `main_timeline` | `run_id`, `agent_kind` |
| `session.message.appended`（agent 回复） | orchestrator/worker LLM 返回后 | `main_timeline` | `content`, `role` |
| `run.completed` | run 状态终态时 | `main_timeline` | `run_id`, `status` |
| `subtask.delegated` | `delegate_tool` 派发时 | `subtask_thread` | `subtask_id`, `task_prompt` |
| `subtask.completed` | worker callback 完成时 | `subtask_thread` | `subtask_id`, `status`, `result_ref` |
| `plan.updated` | plan 写入/更新时 | `main_timeline` | `plan_id`, `summary`, `steps` |
| `workspace.changed` | workspace 文件写操作后 | `workspace_panel` | `paths`（变更文件列表） |

实现上集中一个 `DomainEventEmitter` 辅助（包装 `next_sequence_no` + `create`），在 `AgentRunInputService` 与相关 tool 里调用，避免 sequence_no 计算散落。

### 3. 文件树接口

现有 `WorkspaceSession.list_dir` 只列单层。新增端点按 `path` 参数列出该层目录项（前端 WorkspaceBrowser 本就按需逐层展开，单层返回即可），节点形如 `{type, name, path}`。工作目录从 `source_workspace.root_path` 解析（替代当前的 `TEST_WORKSPACE_PATH`），并复用 `WorkspaceSession.resolve_path` 的越界保护，防止路径逃逸。

## gateway_service 改动

### 1. AgentServiceClient 接成真实 httpx

替换桩实现，基于 `get_settings().agent_service_base_url` 用 httpx 调用 agent_service。需要的方法：

- `list_session_events(session_id, since)` → `GET /sessions/{id}/events?since=N`
- `get_session(id)` / `list_sessions()`
- `get_source_workspace(id)` / `list_source_workspaces()`
- `list_session_workspaces(source_id)` / `get_session_workspace(id)`
- `get_workspace_tree(source_id, path)`
- `get_agent_run(id)`
- 写代理：`create_session`、`post_message`、`create_source_workspace`、`create_session_workspace`、`delete_session`

### 2. SSE tail（gateway 轮询）

`GET /sessions/{id}/stream` 改为轮询型生成器：

```
last_seq = Last-Event-ID（请求头，缺省 0）
while 连接存活:
    events = client.list_session_events(session_id, since=last_seq)
    for e in events:
        yield f"id: {e['sequence_no']}\nevent: {e['event_type']}\ndata: {json.dumps(e['payload'])}\n\n"
        last_seq = e['sequence_no']
    await asyncio.sleep(interval)
```

关键点：

- `data:` 用 `json.dumps` 序列化（当前桩用 f-string 会输出 Python repr，需修正）
- `id:` 用 `sequence_no`，支撑前端 `Last-Event-ID` 续传
- **自适应轮询间隔**：刚拉到新事件时用短间隔（如 300ms），连续空轮则退避到 2s，降低空闲开销
- 客户端断开时退出循环（捕获 `asyncio.CancelledError` / 连接关闭）

> 第一阶段直接在轮询循环里 `yield` 即可；若后续要进一步压低前端侧延迟，可在 gateway 进程内加 `asyncio.Queue`（轮询协程 put、SSE 连接 await get），但本轮不需要。

### 3. 页面聚合接口

- `GET /workspace-page/{source_workspace_id}`：聚合 source 详情 + 其下 session_workspaces + （可选）文件树根层，对应 Workspace 页一次加载
- `GET /session-page/{session_id}`：聚合 session 详情 + 历史 `domain_events`（投影成 main_timeline / subtask_thread / workspace_panel 三块）+ 绑定的 session_workspace 快照，对应 Chat 页选中 session 时一次加载

聚合逻辑只做"领域事实→前端视图"的形状转换，不含编排语义。

### 4. 写代理 + CORS

- 写接口透传到 agent_service：`POST /sessions/{id}/messages`、`POST /sessions`、`POST /source-workspaces`、`POST /session-workspaces`、`POST /sessions/{id}/delete`
- 加 `CORSMiddleware`（前端 dev server 来源），否则浏览器跨域调用与 EventSource 均被拦

## domain_event → 前端 SSE 事件投影

gateway 把领域事件按 `event_scope` 投影到前端三块视图，前端 `EventSource` 按 `event:` 类型分发：

| event_scope | 前端归属 | 前端动作 |
|---|---|---|
| `main_timeline` | Chat 主消息流 | 追加消息 / 更新状态行 |
| `subtask_thread` | 可展开子任务流 | 更新对应 subtask thread |
| `workspace_panel` | 右侧运行态 RuntimePanel | 刷新 workspace 文件/状态摘要 |

前端按 `sequence_no` 去重与排序，重连后用 `Last-Event-ID` 避免重复渲染。

## 前端改动

当前前端为静态 mock。接入时：

1. 新增 `utils/api.js`（`fetchJson` 封装，base URL 指向 gateway）
2. `data/mockChat.js`、`data/mockWorkspace.js` 替换为真实接口调用
3. Chat 页：选中 session 时拉 `session-page` + 开 `EventSource`，发消息走 `POST messages`
4. Workspace 页：拉 `workspace-page`，文件树按需调 tree 接口
5. RuntimePanel：消费 `workspace_panel` / run 状态事件

前端组件结构无需改动，仅替换数据来源——这正是静态框架阶段保留 mock 数据层的目的。

## 非目标（本轮明确不做）

- run 异步化与执行中逐步 emit（token 级 / 进度级实时）——留待后续阶段
- source → session_workspace 的派生机制（拷贝 / git worktree）
- agent_service 内部 pub-sub / 直推 SSE
- WebSocket
- gateway 进程内事件 queue（轮询直接 yield 已够）
- domain_events 的索引优化（当前全表扫描，开发阶段可接受）

## 分步实施建议

1. **agent_service 读接口**：先加 `GET /sessions/{id}/events?since=N` 与 `GET /sessions`、`/sessions/{id}`，打通最小读
2. **agent_service 事件补齐**：加 `DomainEventEmitter`，补 `run.started` / agent 回复 `session.message.appended` / `run.completed`
3. **gateway client + SSE**：`AgentServiceClient` 接 httpx，`/stream` 改轮询型，修正 `data:` JSON 序列化，加 CORS
4. **gateway 聚合**：实现 `session-page` / `workspace-page`
5. **workspace 读**：`source-workspaces` 列表/详情/tree，gateway 透传
6. **前端接入**：替换 mock，Chat 页接 SSE，Workspace 页接 tree
7. **写链路**：`POST messages` 等写代理，端到端验证一条消息从发送到 SSE 回流

每步都可独立验证（agent_service 读接口可 curl，gateway SSE 可用 `curl -N`，前端最后接）。
