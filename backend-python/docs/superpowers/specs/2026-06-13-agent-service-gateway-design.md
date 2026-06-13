# Agent Service 与 Gateway Service 架构设计

## 概述

当前仓库 `backend-python` 已经具备一条可运行的 agent 主链路：

- `AgentRunInputService`
- `RuntimeAssembler`
- `PromptComposer`
- `LoopEngine`
- `delegate_tool`
- `workspace_session`

现有实现已经可以支撑 `orchestrator -> delegate -> worker -> callback` 的内部运行模式，但它仍然偏向“以 run 为中心的 runtime 服务”，还不是“以 session/workspace 为中心的 agent 核心链路服务”。

下一阶段需要让当前仓库 `backend-python` 承载 future `agent_service`，并新增一个面向前端实时交互的 `gateway_service`。两者分工如下：

- `agent_service`：负责 agent 核心链路、资源绑定、状态推进、事件产出
- `gateway_service`：负责前端入口、聚合查询、实时推送、视图事件投影

本设计以最小可实现为原则，不引入第三个 `workspace_service`，不预先设计复杂状态机，不先引入重型消息总线。

## 目标

- 将当前仓库 `backend-python` 的职责明确收敛为 future `agent_service`。
- 引入 `source workspace`、`session workspace`、`session`、`domain event` 四个核心资源模型。
- 让前端 `workspace 页面` 与 `session 页面` 建立清晰的职责边界。
- 保持 `session` 与 `session workspace` 绑定，但两者生命周期不强耦合。
- 支持“主群聊流 + 可展开子任务流 + 右侧 workspace 栏”的前端展示模型。
- 让 `gateway_service` 通过 `domain events` 向前端提供实时反馈。
- 在保持现有 runtime 主链路的前提下，最小化演进，而不是推翻重写。

## 非目标

- 不在本阶段拆出第三个独立 `workspace_service`。
- 不在本阶段设计复杂的 `paused`、`archived`、`stale` 等扩展状态。
- 不在本阶段实现 source workspace 与 session workspace 之间的自动同步或自动合并。
- 不在本阶段支持多个活跃 session 并发共享同一个 `session workspace`。
- 不在本阶段引入复杂 MQ、事件总线或流处理基础设施。
- 不在本阶段设计 branch/merge/PR 的完整 UI 或资源流程。

## 设计结论

### 总体结论

采用“双服务、单核心资源域”的结构：

- `agent_service` 作为 agent 核心链路服务
- `gateway_service` 作为前端交互与实时反馈服务

其中：

- `agent_service` 只输出领域事实，不负责前端展示语义
- `gateway_service` 不承担 agent 编排逻辑，只负责把领域事实转换成前端视图事件

### 为什么采用双服务而不是单服务

单服务内部虽然也可以通过模块分层解决问题，但随着前端页面、实时连接、会话视图和 agent runtime 持续扩展，边界会很容易重新耦合在一起。

当前产品的两个核心责任已经十分明确：

- 一类是 agent 运行、workspace 绑定、tool 调用、delegate、callback、plan 更新
- 一类是前端 session 页面、workspace 页面、SSE 推送、时间线拼装

这两类职责变化频率不同、吞吐特征不同、接口语义也不同。尽早明确为 `agent_service` 和 `gateway_service`，可以避免后续在 API、状态机和事件模型上互相污染。

### 为什么不拆第三个 workspace 服务

虽然 `workspace` 已经具备独立资源域特征，但当前阶段它还没有重到需要单独拆服。

目前真正重要的是先把以下边界定稳：

- `source workspace` 是项目主资源
- `session workspace` 是运行副本资源
- `session` 是对话会话资源
- `agent_service` 负责管理它们的绑定关系与运行语义

因此本阶段将 workspace 资源管理保留在 `agent_service` 内部，后续只有在 workspace 生命周期、同步策略、权限模型显著变复杂时，再考虑独立拆分。

## 领域模型

### 1. SourceWorkspace

`source workspace` 是用户在 `workspace 页面` 手动创建和管理的主项目资源。

职责：

- 表示一个可被管理的项目
- 持有项目的根目录信息或仓库来源信息
- 作为多个 `session workspace` 的父实体
- 作为前端 `workspace 页面` 的默认展示对象

约束：

- 它不是 agent 实际运行的工作副本
- 它不直接承载 session 对话
- 它可以关联多个 `session workspace`

### 2. SessionWorkspace

`session workspace` 是从某个 `source workspace` 派生出来的隔离副本，语义上类似分支，但更准确地说是“可运行的工作副本”。

职责：

- 作为某个 session 的文件运行上下文
- 提供 agent 真正读写和执行的工作目录
- 作为前端右侧 workspace 栏的内容来源
- 允许在 `workspace 页面` 中被查看和管理

约束：

- 同一时刻最多只能被一个 `active session` 占用
- 删除 session 不自动删除它
- 即使没有活跃 session，它也依然可以存在并被查看
- 若用户要继续对话，必须恢复旧 session 或基于该 `session workspace` 新开 session

### 3. Session

`session` 是前端的群聊式对话实体，是用户和 agent 系统交互的主要入口。

职责：

- 绑定一个 `session workspace`
- 承载主群聊时间线
- 作为实时事件订阅的主通道
- 作为 orchestrator 持续协作的对话外壳

约束：

- 一个 session 必须绑定一个 `session workspace`
- session 被删除时，不级联删除 `session workspace`
- 同一 `session workspace` 可以被历史 session 复用，但不能被多个活跃 session 同时使用

### 4. AgentRun

`agent run` 是一次具体的 agent 执行实例，是 session 内部的运行单元。

职责：

- 表示 orchestrator 或 worker 的一次执行
- 保存运行时快照、上下文快照、状态与结果
- 串联 tool 调用、delegate、callback 和 plan 更新

当前代码中已经存在 `AgentRunModel` 与对应 repository，本阶段主要是在 `session` 语义下重新挂接，而不是重写这部分实现。

### 5. Subtask

`subtask` 表示 orchestrator 派发给 worker 的子任务。

职责：

- 记录 delegated task 的状态、结果与引用关系
- 连接主群聊流与可展开子任务流
- 作为前端 thread 的锚点实体

当前 `delegate_tool` 已经具备这条链路的基本雏形，本阶段主要是将其纳入新的 session/domain event 模型。

### 6. DomainEvent

`domain event` 是 `agent_service` 持久化产出的标准领域事件。

职责：

- 记录系统中已经发生的事实
- 作为 `gateway_service` 实时推送和历史回放的唯一上游输入
- 作为 session 页面主群聊流、子任务流、workspace 右侧栏的统一事实来源

这张表是本设计中最关键的新资源之一。没有统一事件事实层，后续前端重连、回放、聚合展示都会变得不稳定。

## 资源关系

本设计采用以下核心关系：

- `1 SourceWorkspace -> N SessionWorkspaces`
- `1 SessionWorkspace -> N Sessions（历史上）`
- `1 SessionWorkspace -> 0..1 ActiveSession（同一时刻）`
- `1 Session -> N AgentRuns`
- `1 OrchestratorRun -> N Subtasks`
- `1 Session / Run / Subtask -> N DomainEvents`

其中最重要的资源约束只有四条：

- `source workspace` 可以拥有多个 `session workspace`
- `session` 必须绑定一个 `session workspace`
- `session workspace` 同一时刻最多只能被一个 `active session` 占用
- 删除 `session` 不自动删除 `session workspace`

## 页面模型

### Workspace 页面

`workspace 页面` 默认只展示 `source workspace`。

它负责：

- 创建和管理 `source workspace`
- 查看 `source workspace` 基本信息
- 展开查看关联的 `session workspaces`
- 创建、删除 `session workspace`
- 查看 `session workspace` 是否正被活跃 session 占用

它不负责：

- 承载实时 agent 对话
- 直接继续 session 内的群聊协作

### Session 页面

`session 页面` 是群聊式协作界面。

它由三块视图组成：

- 主群聊流
- 可展开子任务流
- 右侧 `session workspace` 栏

其中：

- 主群聊流展示对用户有意义的摘要事件
- 子任务流展示 delegated worker 的详细执行内容
- 右侧栏展示当前绑定的 `session workspace` 文件信息与变更摘要

## 展示事件模型

### 主群聊流

主群聊流只展示摘要型事件，避免被 worker 和 tool 的细节淹没。

示例：

- 用户消息
- 协调器回复
- 已派发子任务
- 计划已更新
- 工具执行完成
- 子任务成功或失败

### 子任务流

子任务流在展开某个 delegated task 后展示完整执行细节。

示例：

- worker 的详细执行输出
- tool 参数
- stdout/stderr
- callback 明细
- 失败原因

### Workspace 右侧栏

右侧栏展示当前 session 绑定的 `session workspace` 信息。

示例：

- 文件树
- 最近文件变更摘要
- 当前绑定状态

## 最小状态设计

本阶段只保留最小可实现状态，不为未来扩展提前设计复杂状态机。

### SourceWorkspace 状态

- `ready`
- `deleted`

### SessionWorkspace 状态

- `ready`
- `attached`
- `deleted`

### Session 状态

- `active`
- `deleted`

这组状态已经足够表达当前产品语义，不额外引入 `paused`、`archived`、`stale`、`materializing` 等扩展状态。

## 最小生命周期流转

### 新建 Session

1. 用户在 `workspace 页面` 选定一个 `source workspace`
2. 选择一个已有 `session workspace`，或创建一个新的 `session workspace`
3. `gateway_service` 调用 `agent_service`
4. `agent_service` 校验该 `session workspace` 是否可用、是否已被其他活跃 session 占用
5. 创建 `session`，状态为 `active`
6. 将 `session workspace` 标记为 `attached`

### 删除 Session

1. 前端发起删除 session
2. `gateway_service` 调用 `agent_service`
3. `agent_service` 将 `session` 标记为 `deleted`
4. 如果该 session 当前占用了某个 `session workspace`，则将其状态从 `attached` 释放为 `ready`

删除 session 只释放占用关系，不删除 `session workspace` 本体。

### 基于 SessionWorkspace 继续工作

若某个 `session workspace` 仍存在，则用户可以：

- 继续使用一个尚未删除、且当前仍合法绑定该 `session workspace` 的 session
- 或基于该 `session workspace` 新建一个新的 session

若旧 session 已被删除，则不能继续使用该 session 本身，只能基于该 `session workspace` 新开 session。

## 服务边界

### Agent Service

`agent_service` 是系统的大脑，负责领域内真实业务行为。

职责：

- 管理 `source workspace`
- 管理 `session workspace`
- 管理 `session`
- 管理 `agent run`、`subtask`、`plan`
- 驱动 orchestrator / worker / delegate / callback
- 持久化 `domain events`
- 对外提供命令接口和基础查询接口

它不负责：

- SSE/WebSocket 长连接管理
- 前端页面聚合视图
- UI 事件格式
- 前端连接态处理

### Gateway Service

`gateway_service` 是前端适配层，不承担 agent 编排逻辑。

职责：

- 作为前端唯一入口
- 提供 `workspace 页面` 聚合接口
- 提供 `session 页面` 聚合接口
- 建立 SSE 实时连接
- 订阅或读取 `agent_service` 产出的 `domain events`
- 将领域事件转换成前端视图事件

它不负责：

- 工具执行
- workspace 派生逻辑
- delegate 决策
- worker 调度语义

### 边界原则

本设计遵守一条最重要的边界原则：

- `agent_service` 输出事实
- `gateway_service` 输出视图

也就是说：

- `agent_service` 只关心“发生了什么”
- `gateway_service` 只关心“前端应该如何看到这件事”

## 最小数据模型

### source_workspaces

建议字段：

- `source_workspace_id`
- `name`
- `root_path` 或等效来源信息
- `status`
- `created_at`
- `updated_at`

### session_workspaces

建议字段：

- `session_workspace_id`
- `source_workspace_id`
- `name`
- `root_path`
- `status`
- `origin_session_workspace_id` 可选
- `created_at`
- `updated_at`

其中 `origin_session_workspace_id` 仅作为未来扩展保留字段，本阶段不依赖它实现主链路。

### sessions

建议字段：

- `session_id`
- `session_workspace_id`
- `title`
- `status`
- `created_at`
- `updated_at`
- `deleted_at` 可选

### agent_runs

当前 `agent_runs` 已有雏形，建议最终明确挂在 `session` 之下。

建议至少包含：

- `run_id`
- `session_id`
- `agent_id`
- `role`
- `agent_kind`
- `session_workspace_id`
- `parent_run_id`
- `root_run_id`
- `status`
- `context_snapshot`
- `runtime_snapshot`
- `created_at`
- `updated_at`

当前代码中的 `workspace_id` 建议后续明确重命名或语义收敛为 `session_workspace_id`，以避免和 `source_workspace_id` 混淆。

### subtasks

建议字段：

- `subtask_id`
- `session_id`
- `root_run_id`
- `parent_run_id`
- `worker_run_id`
- `status`
- `title` 可选
- `task_prompt`
- `result_ref` 可选
- `created_at`
- `updated_at`

### domain_events

建议字段：

- `event_id`
- `session_id`
- `session_workspace_id`
- `run_id` 可选
- `subtask_id` 可选
- `event_type`
- `event_scope`
- `payload`
- `sequence_no`
- `created_at`

`event_scope` 最小建议只分三类：

- `main_timeline`
- `subtask_thread`
- `workspace_panel`

## API 边界建议

### Agent Service API

`agent_service` 提供命令接口和基础查询接口。

命令接口示例：

- `POST /source-workspaces`
- `POST /session-workspaces`
- `POST /sessions`
- `POST /sessions/{session_id}/messages`
- `POST /sessions/{session_id}/delete`
- `POST /session-workspaces/{id}/delete`

基础查询接口示例：

- `GET /source-workspaces/{id}`
- `GET /session-workspaces/{id}`
- `GET /sessions/{id}`
- `GET /sessions/{id}/subtasks`
- `GET /sessions/{id}/events`

这些查询接口用于暴露领域原始数据，不直接承担前端页面聚合语义。

### Gateway Service API

`gateway_service` 提供前端友好的聚合查询与实时接口。

聚合接口示例：

- `GET /workspace-page/{source_workspace_id}`
- `GET /session-page/{session_id}`

实时接口示例：

- `GET /sessions/{session_id}/stream`

本阶段建议优先采用 `HTTP + SSE` 组合：

- 写操作通过 HTTP 完成
- 聚合读接口通过 HTTP 完成
- 实时事件推送通过 SSE 完成

这样可以在保持实现简单的前提下，满足前端实时群聊反馈的主要需求。

## 事件流模型

本设计不要求 `agent_service` 直接维护前端连接，而是要求它稳定产出 `domain events`。

推荐的最小事件链路：

1. 前端向 `gateway_service` 发起 HTTP 请求
2. `gateway_service` 调用 `agent_service`
3. `agent_service` 驱动 session 内部执行
4. 执行过程中写入 `domain_events`
5. `gateway_service` 订阅、读取或轮询新的 `domain_events`
6. `gateway_service` 将其转换成前端 SSE 事件
7. 前端更新主群聊流、子任务流和右侧 workspace 栏

### 最小事件类型

建议先只保留足以支撑 UI 的最小事件集合：

- `session.message.appended`
- `run.started`
- `run.completed`
- `subtask.delegated`
- `subtask.completed`
- `tool.started`
- `tool.completed`
- `plan.updated`
- `workspace.changed`
- `session.deleted`

这组事件已经足够覆盖：

- 主群聊流
- 子任务流
- 右侧 workspace 栏

## 与当前仓库 backend-python 的演进关系

当前代码中可直接复用的核心部分包括：

- `AgentRunInputService`
- `RuntimeAssembler`
- `PromptComposer`
- `LoopEngine`
- `delegate_tool`
- `workspace_session`
- `agent_run`、`subtask`、`input_event`、`plan` 相关基础模型与 repository

本次演进不是推翻 runtime 主链路，而是让当前仓库 `backend-python` 从“run 驱动的内部执行服务”升级为“session/workspace 驱动的 future `agent_service`”。

### 当前模型到目标模型的映射

为了避免目标设计和当前实现脱节，本节明确说明现有模型在新架构中的去向。

#### `agent_run`

当前状态：

- 已经是系统内部最核心的执行实体
- 已具备 `parent_run_id`、`root_run_id`、`status`、`context_snapshot`、`runtime_snapshot`
- 当前通过 `workspace_id` 绑定运行上下文

目标定位：

- 继续保留为“执行实例”模型
- 不升级为前端会话实体
- 由当前“直接对外暴露的主资源”收敛为“挂在 `session` 之下的内部执行资源”

建议改动：

- 新增 `session_id`
- 将当前 `workspace_id` 的语义收敛为 `session_workspace_id`
- 保留现有 `parent_run_id` / `root_run_id` 结构，继续服务 orchestrator/worker 链路

也就是说，`agent_run` 不会被新模型替代，而是会被重新挂接到 `session` 这一层之下。

#### `input_event`

当前状态：

- 已承担 run 的入站事件记录
- 当前只覆盖两类输入：
  - `user_input`
  - `worker_callback`

目标定位：

- 继续保留
- 继续承担“谁向某个 run 输入了什么”的职责
- 不扩展为前端实时展示事件总表

职责边界：

- `input_event` 负责记录输入
- `domain_event` 负责记录系统内部已经发生的事实

这个边界很重要。否则后续会把“用户输入了一条消息”和“系统已经派发了一个 subtask”混在同一张语义不清晰的表里。

#### `subtask`

当前状态：

- 已经是 `delegate_tool` 主链路的一部分
- 已具备 `parent_run_id`、`worker_run_id`、`status`、`task_prompt`、`result_ref`

目标定位：

- 继续保留为 delegated work 的领域实体
- 前端上对应“可展开子任务流”的 thread 锚点

建议改动：

- 新增 `session_id`
- 保持与 `root_run_id` / `parent_run_id` / `worker_run_id` 的关联不变

也就是说，`subtask` 不是新的附属模型，而是会从“内部执行记录”提升为“前端 thread 也会直接依赖的核心实体”。

#### `plan`

当前状态：

- 已具备 plan 文件落地与 run 绑定能力
- 当前更多是 runtime/tool 执行结果的一部分

目标定位：

- 继续保留为 orchestrator 计划产物
- 不单独升级成一条新的顶层资源线

建议改动：

- 初期不强行改造 plan 模型
- 仍然围绕 run 产出与更新
- 如需让前端主群聊流感知 plan 变化，由 `domain_event` 记录 `plan.updated`

这意味着本阶段重点不是重做 plan 模型，而是让 plan 的变化能被 session 页面看见。

#### `domain_event`

当前状态：

- 当前系统还没有独立的“事实事件层”
- 现有 `input_event` 只能表达输入，不能完整表达系统执行过程中发生的事实

目标定位：

- 新增一个最小事件记录层
- 专门服务于：
  - session 主时间线
  - subtask thread
  - SSE 补发与断线重连

第一阶段不应把 `domain_event` 设计成复杂的事件中心，而应收敛为一个最小事实表。

第一阶段建议仅记录少量高价值事件：

- `session.message.appended`
- `subtask.delegated`
- `subtask.completed`
- `plan.updated`
- `workspace.changed`

这几个事件已经足够支撑：

- 主群聊流的最小更新
- 子任务流的创建和完成
- workspace 右侧栏的刷新依据

因此，`domain_event` 在本设计里不是用来替代 `input_event`，而是补足“系统事实输出层”。

### 与当前临时存储实现的关系

当前代码仍使用 `InMemoryStore` 作为临时存储实现，其中只有：

- `agents`
- `agent_runs`
- `input_events`
- `subtasks`
- `plans`

这说明当前实现仍然是典型的 runtime 中心模型，而不是 session/workspace 中心模型。

但 `InMemoryStore` 只应被视为当前开发阶段的临时承载方式，不应作为目标架构的正式存储方案。

本设计明确建议后续采用 `SQLite` 作为第一阶段正式持久化存储，替代当前内存字典存储。

采用 `SQLite` 的原因：

- 比内存存储更符合 `session`、`workspace`、`event` 这类资源的持久化需求
- 实现成本远低于一开始引入更重的数据库系统
- 足以支撑当前阶段的单机开发、调试、基础查询和事件回放需求
- 更适合为 `gateway_service` 的 SSE 补发与聚合查询提供稳定数据来源

因此本设计新增的：

- `source_workspaces`
- `session_workspaces`
- `sessions`
- `domain_events`

本质上是在现有临时存储结构外补齐产品层资源，而不是否定现有 `agent_runs`、`input_events`、`subtasks`、`plans` 的价值。

更准确地说：

- `agent_runs`、`input_events`、`subtasks`、`plans` 继续保留为运行内核资源
- `source_workspaces`、`session_workspaces`、`sessions`、`domain_events` 补齐为产品层与事件层资源
- 第一阶段将这些资源统一落到 `SQLite`，不再继续扩展 `InMemoryStore`

因此建议的改造方向是：

- 补齐 `source workspace`
- 补齐 `session workspace`
- 补齐 `session`
- 补齐 `domain event`
- 将现有 `agent_run_create/input` 收编到新的 `session` 语义之下
- 再在外层引入 `gateway_service`

## 分阶段实施建议

### 阶段 1：将当前仓库 `backend-python` 收敛为 future agent_service

目标：

- 补齐 `source workspace`、`session workspace`、`session`、`domain event`
- 让 `agent_run` 明确挂到 `session`
- 收敛 `workspace_id` 语义到 `session_workspace_id`

### 阶段 2：补齐 session 主链路

目标：

- 支持创建 session
- 支持向 session 发送消息
- 支持删除 session
- 支持最小 `domain event` 写入
- 保持现有 orchestrator/worker/tool loop 可复用

### 阶段 3：增加 gateway_service

目标：

- 提供 `workspace 页面` 聚合接口
- 提供 `session 页面` 聚合接口
- 提供 SSE 实时流
- 实现 `domain event -> UI event` 的最小投影

### 阶段 4：补强体验，不增加重架构

目标：

- 优化 `session workspace` 占用校验
- 优化 session 恢复逻辑
- 优化文件变更摘要
- 优化子任务线程展示

## 明确暂不做的内容

为防止设计范围失控，本阶段明确不做以下内容：

- 第三个独立 `workspace_service`
- 复杂状态机
- 自动同步 source workspace
- 多活跃 session 共享一个 `session workspace`
- 重型 MQ 或复杂事件总线
- 完整 branch/merge/PR 流程
- CRDT 或多人实时协同编辑模型
- 删除 session 时自动联动清理全部资源

## 最终建议

本设计建议正式采用以下主线：

- 当前仓库 `backend-python` 演进为 future `agent_service`
- 新增 `gateway_service` 作为前端实时和聚合层
- 数据模型先补四个核心资源：
  - `source workspace`
  - `session workspace`
  - `session`
  - `domain event`
- 前端模型固定为：
  - `workspace 页面` 管理 `source workspace`
  - `session 页面` 绑定 `session workspace`
  - `主群聊流 + 可展开子任务流 + 右侧 workspace 栏`
- 实时传输先采用：
  - HTTP + SSE
- 状态先保持最小化：
  - `ready / attached / deleted`
  - `active / deleted`

这条路线能以最小成本把当前 runtime 后端提升为真正的 agent 核心链路服务，同时为前端实时协作提供清晰稳定的 gateway 边界。
