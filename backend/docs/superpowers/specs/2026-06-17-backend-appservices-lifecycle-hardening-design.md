# Backend AppServices Lifecycle Hardening Design

## 概述

本设计聚焦 `backend/` 当前第一阶段主链之外的工程收口问题，目标是在不引入产品级用户系统的前提下，统一应用生命周期、app state、依赖装配与 runtime principal 来源。

本轮解决的问题是：

- `main.py` 仍使用 `@app.on_event(...)`，测试持续出现 deprecation warning
- `app.state` 只挂载了零散对象，没有结构化 app-level service container
- API 层到处直接 `get_redis_client()` 并现场拼装 repository / runtime / service
- AgentScope runtime 所需的技术性主体标识仍散落为字符串字面量 `default-user`

本轮不引入真实用户体系，也不做认证鉴权。对于这个本地单用户应用，统一使用固定 runtime principal `local-user` 即可。

## 范围

### 本轮纳入

- 将 app lifecycle 从 `@app.on_event("startup"/"shutdown")` 迁移到 lifespan
- 引入结构化 app-level dependency container：`AppServices`
- 统一 app state 挂载方式
- 统一 `Redis`、`ChatRunRegistry`、runtime principal `local-user` 的创建与访问
- 收口 API 层 service/repository/runtime 的装配方式
- 将 `default-user` 统一替换为 `local-user` provider
- 为上述行为补充测试

### 本轮明确不纳入

- 真实 auth / 登录用户体系
- 多用户支持
- logging / tracing 系统化增强
- 全量错误模型统一
- Team worker/subagent 深化

## 问题确认

### 1. 生命周期仍是旧式 `on_event`

当前 `backend/app/main.py` 使用：

- `@app.on_event("startup")` 确保 default team
- `@app.on_event("shutdown")` 关闭 chat registry

功能上可用，但：

- FastAPI 已给出 deprecation warning
- 生命周期资源无法结构化集中管理
- `Redis client / AppServices / runtime principal` 这类 app-scope 资源没有统一装配入口

### 2. 依赖装配分散且重复

当前 API 路由普遍采用以下模式：

- 每次请求重新调用 `get_redis_client()`
- 每个 router 自己拼 repository / runtime / service
- `sessions.py` 中已开始出现 `factory + inline service assembly` 的复杂度堆叠

这使得：

- service wiring 难以统一修改
- 测试中难以替换依赖
- 生命周期对象和请求级对象边界不清晰

### 3. `default-user` 不是产品需求，而是 runtime 技术键

本应用是本地单用户应用，不需要产品层 `user_id`。但 AgentScope runtime 的 session / state / message 存储读取仍依赖一个稳定主体标识。

当前问题不是“必须做用户系统”，而是：

- `default-user` 作为 runtime technical principal 散落在多个 service 中
- 字面量重复，后续演进成本高
- 语义上与产品层“登录用户”混淆

因此本轮将其收口为固定 runtime principal：`local-user`。

## 设计原则

### 1. 不引入产品级用户体系

本轮不新增登录、会话、身份认证等概念。

`local-user` 仅表示：

- AgentScope runtime 的技术分区键
- 本地单用户应用中唯一固定主体

它不是产品界面中的用户模型。

### 2. App-scope 资源统一由 `AppServices` 管理

应用级资源应只在 app lifecycle 中创建一次，再通过结构化容器暴露给路由层。

本轮不追求重型 DI 框架；使用轻量 `AppServices` 即可。

### 3. 路由层只负责“取 service + 调用 + 映射 HTTP 错误”

路由层不再负责：

- 直接 new repository
- 直接 new runtime
- 拼装 runtime factory
- 管理 app-scope 对象

### 4. 请求级 service 可以复用 app-scope 单例依赖，但不共享错误的事件循环资源

本轮要维持上一轮 async mainline 的经验：

- app-scope 可以集中管理依赖创建入口
- 但后台任务所需的 runtime/repository 仍应通过 fresh factory 生成，避免跨 event loop 复用错误对象

因此 `AppServices` 的职责不是“所有对象都只创建一次”，而是“统一提供正确的创建策略”。

## 目标结构

### 1. `AppServices`

新增 `AppServices` 作为 app-level service container。

它至少负责持有或提供：

- `settings`
- `redis`
- `chat_run_registry`
- `runtime_principal`，固定值 `local-user`

以及以下构造入口：

- `session_repository()`
- `team_repository()`
- `workspace_repository()`
- `state_runtime()`
- `chat_runtime()`
- `confirm_runtime()`
- `runtime_bootstrap_service()`
- `session_service()`
- `session_query_service()`
- `runtime_service()`
- `team_service()`
- `team_query_service()`
- `workspace_service()`
- `workspace_query_service()`

关键边界：

- `AppServices` 可以返回新对象
- 也可以返回共享对象
- 但调用方不需要知道构造细节

### 2. Runtime Principal

新增一个统一 provider，例如：

- `AppServices.runtime_principal == "local-user"`

所有需要与 AgentScope runtime 交互的 service，都从这里拿 principal，而不是写死 `default-user`。

影响范围包括：

- session create runtime session
- send message
- submit waiting item / continue confirm
- query runtime messages
- runtime session read/write

### 3. Lifespan

`main.py` 改为使用 FastAPI lifespan：

启动阶段：

- 读取 settings
- 创建 Redis client
- 创建 `ChatRunRegistry`
- 创建 `AppServices`
- 挂载到 `app.state.services`
- ensure default team

关闭阶段：

- 关闭 `ChatRunRegistry`
- 关闭 Redis client

### 4. App State

`app.state` 的公开结构改为：

- `app.state.services`

不再要求路由层直接知道：

- `chat_run_registry`
- `redis`
- `settings`

这些都由 `AppServices` 封装。

## 组件改动

### 1. `backend/app/main.py`

改动内容：

- 切换到 lifespan
- 启动时构造 `AppServices`
- 调用 `services.team_service().ensure_default_team()`
- 关闭时释放 registry 和 Redis client

### 2. 新增 `backend/app/application/services.py` 或等价位置

新增 `AppServices` 定义。

职责：

- 保存 app-scope 资源
- 作为 repository/runtime/service 的统一 provider
- 提供 runtime principal `local-user`
- 对 `RuntimeService` 提供正确的 fresh factory

### 3. `backend/app/api/*.py`

路由层改为从 `request.app.state.services` 或无请求场景下的 app services provider 取 service。

其中：

- `sessions.py` 是收益最大的收口点
- `teams.py` / `workspaces.py` 也应同步收口，避免半套模式并存

### 4. `backend/app/services/*.py`

所有 runtime 相关 service 去掉散落的 `default-user`，改为接收：

- `runtime_principal: str`

或接收一个 principal provider。

本轮优先采用直接注入字符串，保持最小实现复杂度。

### 5. `backend/app/config.py`

可新增一个显式配置项，例如：

- `local_runtime_principal: str = "local-user"`

这样既满足当前固定值，也为未来演进留出唯一入口。

## 测试策略

### 1. lifecycle / app state

增加或修改测试以验证：

- `create_app()` 后 lifespan 能构造 `app.state.services`
- `AppServices.runtime_principal == "local-user"`

### 2. runtime principal 统一性

增加测试验证：

- create session 时 runtime session 使用 `local-user`
- query / send / waiting / cancel 路径中的 runtime 调用使用的也是 `local-user`

### 3. 依赖装配收口

增加测试验证：

- 路由层能通过 `AppServices` 获取 service
- 原有 session/team/workspace/app 测试不回归

### 4. TDD 顺序

必须先写失败测试，再改实现：

1. app lifecycle / services container 测试
2. runtime principal 测试
3. router wiring 测试
4. 实现 `AppServices` + lifespan
5. 回归现有 backend 测试

## 风险与取舍

### 1. 不做重型 DI

本轮故意不引入额外容器框架，避免把“工程收口”升级成基础设施迁移。

### 2. 保留部分请求级对象构造

尽管 `AppServices` 统一了入口，但部分 runtime/repository 在后台任务场景仍需要 fresh instance。这是刻意保留的正确复杂度，不是未完成。

### 3. `local-user` 仍然是固定值

这是本轮明确接受的取舍：

- 它不是产品用户模型
- 它只是 runtime technical principal
- 对本地单用户应用完全足够

## 验收标准

满足以下条件即认为本轮完成：

- `main.py` 不再使用 `@app.on_event(...)`
- app 启动后存在结构化 `app.state.services`
- runtime technical principal 统一为 `local-user`
- 代码中不再散落 `default-user` 字面量
- API 层 service/repository/runtime 装配显著收口到 `AppServices`
- 相关测试与 `ruff` 通过
