# 创建 Workspace / 创建 Session 补全 + 前端接入 实现计划

**日期：** 2026-06-15
**分支：** feat/agent-service-gateway-restructure（沿用）

## 背景与目标

补全两条创建链并接到前端，让用户能在界面上：
1. **创建 source workspace**（指定本地目录）
2. **创建 session**（选一个 source → 后端自动派生 session workspace → 建会话）

承接上一轮已完成的 `derive_from_source` 后端语义。

## 已与用户对齐的决策

- **建 session 用后端组合端点（原子）**：新增 `POST /sessions/from-source {source_workspace_id, title}`，后端一步内完成「派生 session workspace → 建 session」；前端只调一次，失败不留半成品。
- **建 source 时即校验本地路径存在**：`SourceWorkspaceService.create` 校验 `root_path` 存在且是目录，否则 `ValueError → 400`。
- **前端自建轻量 Modal**（纯 React + CSS，无新依赖），建 source / 建 session 各一个表单。
- **session 派生不复用**（沿用上轮：`origin_session_workspace_id=None`）。

## 后端改动

### 1. source 创建校验（agent_service）
- `services/source_workspace_service.py`：`create` 中校验 `Path(root_path).expanduser().is_dir()`，否则 `raise ValueError(...)`。
- `api/source_workspace.py`：`POST ""` 包 `try/except ValueError → HTTPException(400)`。
- 风险：现有测试 `test_source_workspace_service.py` 用 `tmp_path`（存在），不受影响；`test_workspace_read_api.py` 等用 `SourceWorkspaceRepository().create(...)` 直接入库、不走 service，也不受影响。需确认无测试用 service 建不存在路径。

### 2. session 组合端点（agent_service）
- `services/session_service.py`：新增
  ```
  def create_from_source(self, source_workspace_id: UUID, title: str) -> SessionResponse:
      # 1. 复用 SessionWorkspaceService.derive_from_source(source_id) → 派生副本（含 source 存在性 + 路径校验）
      # 2. 复用现有 create(SessionCreateRequest{session_workspace_id=派生id, title}) → 建 session + 落 session_created 事件
  ```
  注入 `session_workspace_service: SessionWorkspaceService | None = None`（默认 new），便于测试。
- `schemas/session.py`：新增 `SessionFromSourceRequest{source_workspace_id: UUID, title: str}`。
- `api/session.py`：新增 `POST /sessions/from-source`（`ValueError → 400`）。
- 现有 `POST /sessions`（要求 session_workspace_id）保留不动，非破坏。

### 3. gateway 代理补齐
- `client/agent_service_client.py`：加 `create_session_from_source(body)` → `POST /sessions/from-source`；加 `derive_session_workspace(body)` → `POST /session-workspaces/derive`（备用）。
- `api/write_proxy.py`：加 `POST /sessions/from-source`、`POST /session-workspaces/derive` 两个转发。
- `api/read_proxy.py`：已暴露 `/sessions`、`/source-workspaces`，足够；无需新增。
- 注意：source 创建写代理 `POST /source-workspaces` 已存在，会透传 agent_service 的 400。

## 前端改动

### 4. API 接入层（utils/api.js）
新增：
- `createSourceWorkspace({name, root_path})` → `POST /source-workspaces`
- `createSessionFromSource({source_workspace_id, title})` → `POST /sessions/from-source`

### 5. 轻量 Modal 组件（新建 components/Modal/）
- `Modal.jsx` + `Modal.css`：受控 `open/onClose/title/children`，遮罩 + ESC 关闭 + 阻止冒泡。纯 React，无依赖。

### 6. 建 session UI（Chat 页）
- `SessionList.jsx`：「新建 Session」按钮 `onClick` → 触发 `onCreateSession`（提到 Chat 页）。
- `Chat.jsx`：
  - 持 source 列表（启动时 `listSourceWorkspaces`，供下拉选择）
  - 弹 Modal 表单：输入 title + 选 source 下拉 → 调 `createSessionFromSource` → 成功后刷新会话列表并选中新 session
  - 表单提交中 `creating` 态、错误提示。

### 7. 建 source workspace UI（Workspace 页）
- `WorkspaceBrowser.jsx`：「新建」按钮 `onClick` → 触发 `onCreateSource`（提到 Workspace 页）。
- `Workspace.jsx`：
  - 弹 Modal 表单：输入 name + root_path（本地目录）→ 调 `createSourceWorkspace` → 成功后刷新 source 列表
  - 路径无效（400）时显示后端 detail 错误。

## TDD / 验证步骤

### Step 1：source 校验（后端 TDD）✅
- [x] `test_source_workspace_service.py`：不存在路径 / 文件路径 → `ValueError`
- [x] 新增 `test_source_workspace_api.py`：无效路径 → 400
- [x] 实现校验（`Path.is_dir()`）+ 端点 try/except

### Step 2：session 组合端点（后端 TDD）✅
- [x] `test_session_service.py`：`create_from_source` 派生副本 + 建 session + 落事件；source 缺失 → ValueError
- [x] `test_session_api.py`：`POST /sessions/from-source` 200（派生 workspace 真实存在）；source 缺失 → 400；并修正既有用例改用 tmp 目录（适配新校验）
- [x] 实现 `SessionFromSourceRequest` + `create_from_source`（复用 derive + create）+ 端点

### Step 3：gateway 代理（后端 TDD）✅
- [x] `test_write_proxy.py`：`/sessions/from-source`、`/session-workspaces/derive` 透传 + **上游 4xx 透传**
- [x] client 方法 + 路由 + main.py 全局 `httpx.HTTPStatusError` 处理器（透传上游状态码与 body）

### Step 4：前端 ✅
- [x] `components/Modal/`（纯 React + CSS，无新依赖）
- [x] api.js：`createSessionFromSource`、`createSourceWorkspace`
- [x] SessionList + Chat：建 session 弹窗（选 source 下拉 → from-source → 刷新并选中）
- [x] WorkspaceBrowser + Workspace：建 source 弹窗（name + 本地路径 → 刷新列表）
- [x] `npm run build` + `npm run lint` 全绿

### Step 5：端到端冒烟 + 单次总提交 ✅
- [x] 起双服务冒烟：建 source（有效 200 / 无效 400 带真实消息）→ from-source 建 session（自动派生）→ 新 session 发消息 → 真实 LLM 回 "READY" 经 SSE 回流（id:1..5）；workspace-page 见派生 session workspace
- [x] **冒烟暴露并修复真实 bug**：gateway 写代理把 agent_service 的 400 包成 500 → 加全局 httpx 异常处理器透传
- [x] 后端非 e2e 全套 148 passed；改动文件零新增 ruff 违规；前端 build+lint 绿
- [ ] 单次总提交（执行中）

## 验收标准
1. 界面「新建」按钮可用：建 source（校验路径）、建 session（选 source 自动派生）
2. `POST /sessions/from-source` 原子完成派生+建会话；source 缺失/路径无效 → 400
3. 新建 session 后能立即进入并发消息、SSE 回流
4. 后端非 e2e 测试全绿、前端 build+lint 绿、零新增 lint 违规

## 范围纪律（本轮不做）
- 不接 git clone（source 仍只本地目录）
- 不做 source/session 的编辑、删除 UI（删除后端已有，UI 留待后续）
- 派生仍全量复制（不排除 .git/node_modules）
- 不做 RuntimePanel 的 task_status/plan_steps 真数据、文件内容预览
