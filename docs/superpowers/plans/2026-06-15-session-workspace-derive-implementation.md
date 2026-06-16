# Session Workspace 派生（后端语义）实现计划

**日期：** 2026-06-15
**分支：** feat/agent-service-gateway-restructure（沿用）

## 背景与范围（已与用户对齐）

设计文档里 Session Workspace 对应 "Agent Sandbox"——**基于项目源的隔离副本**，`SessionWorkspaceModel.origin_session_workspace_id` 字段即为此预留。当前代码只有"裸建一条记录"的 `SessionWorkspaceService.create`（不复制任何文件，`root_path` 由调用方硬塞），**没有真正的派生语义**。

用户拍板的本轮范围（**严格收窄**）：
- ✅ 只做"**基于 source workspace 自动派生一个新 session workspace**"的**后端语义**
- ✅ source 地址先支持**本地已存在目录**；git clone 留待后续（用户指出：git 本质也是先 clone 到本地再读，核心一致）
- ✅ 派生即**新建副本，不复用**已有 session workspace
- ❌ 不做前端创建 UI（下一轮）
- ❌ 不改 session 创建流程（`POST /sessions` 维持现状）
- ❌ 不碰 git / worktree / 沙箱镜像

## 设计决策

### 1. 受管目录约定
派生出的副本要落到一个平台受管根目录，而非用户随意指定。新增配置：

- `agent_service/app/config.py`：`session_workspace_root: str = "./.AgentHub/session-workspaces"`
- 每个派生副本目录：`<session_workspace_root>/<session_workspace_id>/`

`.AgentHub/` 已在上一轮加入 `.gitignore`，副本不会误入库。

### 2. 复制策略（关键小决策，已向用户点明）
用 `shutil.copytree(source.root_path, dest)` **忠实全量复制**整个目录树。
- 取舍：会把 `.git`、`node_modules` 等重目录一起拷。
- 理由：最简单、最不意外，符合"隔离副本"语义。排除规则留待后续（接 git 后改为 clone/checkout 自然规避）。
- 计划注明此限制，不在本轮做排除清单。

### 3. 派生方法与端点
**Service**（`session_workspace_service.py`，新增方法，不动现有 `create`）：

```
def derive_from_source(self, source_workspace_id: UUID, name: str | None = None) -> SessionWorkspaceResponse:
    1. 读 SourceWorkspaceRepository.get_by_id；None → raise ValueError("source workspace not found")
    2. 校验 source.root_path 存在且是目录；否则 raise ValueError
    3. new_id = uuid4()；dest = Path(settings.session_workspace_root)/str(new_id)
    4. dest.parent.mkdir(parents=True, exist_ok=True)
    5. shutil.copytree(source.root_path, dest)
    6. SessionWorkspaceModel(session_workspace_id=new_id, source_workspace_id=source_id,
         name=name or f"{source.name}-{new_id前8位}", root_path=str(dest),
         status="ready", origin_session_workspace_id=None)  # 不复用 → None
    7. repository.create(model)；return SessionWorkspaceResponse
```

注入：构造器加 `source_repository: SourceWorkspaceRepository | None = None`（默认 new），便于测试。

**Schema**（`schemas/session_workspace.py`，新增请求模型）：
```
class SessionWorkspaceDeriveRequest(BaseModel):
    source_workspace_id: UUID
    name: str | None = None
```

**API**（`api/session_workspace.py`，新增路由，与现有 `POST ""` 并存）：
```
@router.post("/derive")
def derive_session_workspace(payload: SessionWorkspaceDeriveRequest):
    try:
        return get_service().derive_from_source(payload.source_workspace_id, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

### 4. 现有代码保持不变
- `SessionWorkspaceService.create`（裸建）保留——测试和手工链路仍用它，非破坏性。
- 不动 `SourceWorkspaceService`、`POST /sessions`、gateway、前端。

## TDD 任务步骤

### Step 1：配置项
- [ ] `config.py` 加 `session_workspace_root`，`.env.example` 补一行注释（可选）

### Step 2：Schema（先写测试）
- [ ] 在 `test_session_workspace_service.py` 加派生测试（见 Step 3 合并）
- [ ] `schemas/session_workspace.py` 加 `SessionWorkspaceDeriveRequest`

### Step 3：Service 派生方法（TDD）
- [ ] 新测试 `test_derive_from_source_copies_tree`：
  - 在 tmp_path 造 source 目录（含 `main.py` + 子目录 `pkg/mod.py`），建 SourceWorkspace 入库
  - monkeypatch / 覆盖 `session_workspace_root` 指向 tmp_path
  - 调 `derive_from_source(source_id)`
  - 断言：返回 `root_path` 下 `main.py`、`pkg/mod.py` 真实存在且内容一致；`source_workspace_id` 正确；`origin_session_workspace_id is None`；`status == "ready"`
- [ ] 新测试 `test_derive_from_missing_source_raises` / `test_derive_when_root_path_absent_raises`
- [ ] 确认失败 → 实现 `derive_from_source` → 通过

### Step 4：API 端点（TDD）
- [ ] 新测试 `test_derive_session_workspace_api`（TestClient，bootstrap）：POST `/session-workspaces/derive` 返回 200 + 副本字段；source 不存在 → 400
- [ ] 实现路由 → 通过

### Step 5：验证 + 单次总提交
- [ ] `pytest agent_service/tests/test_session_workspace_service.py agent_service/tests/test_*session_workspace*` + 相关 API 测试
- [ ] ruff 仅对改/新建文件，确认零新增违规
- [ ] **不做分步 commit**；全部通过后单次总提交

## 验收标准
1. `POST /session-workspaces/derive {source_workspace_id}` → 在受管目录生成真实副本，文件可读，返回新 session workspace
2. source 不存在或 root_path 不存在 → 400，不留半成品目录（copytree 失败前已校验）
3. 现有测试全绿，零新增 lint 违规
4. 前端、session 创建流程、git 均未触碰（范围纪律）

## 已知限制（本轮明确不做）
- 全量复制，不排除 `.git`/`node_modules`
- 不接 git clone（source 仅本地目录）
- 无前端 UI；session 创建仍需已存在的 session_workspace_id
- 副本目录的清理/回收未做（依赖 `.AgentHub/` 整体忽略）
