# AgentScope Session-Team Backend Architecture Design

## 概述

本设计定义 `backend/` 第一阶段的一体式后端架构。它不是对旧 `backend-python` 的迁移复刻，而是基于 AgentScope 的运行时能力重新设计一个 `session-first` 的工程协作后端。

本设计的目标是：

- 以 `Session` 作为产品顶层主线程
- 以 `Team` 作为协作组织模型
- 以 `Workspace` 作为独立产品资源，并在创建 session 时显式选择
- 以 AgentScope 作为运行时内核，复用其 agent loop、session state、stream、context compression、observe、confirm/resume、workspace、message bus 等能力
- 使用 Redis 作为第一期的核心运行时与产品资源存储底座
- 为前端提供 `Session / Workspace / Team` 三栏结构，以及 session 页面右侧运行态栏

本设计明确不保留旧 `agent_service + gateway_service + run` 这套结构，也不再自研一套与 AgentScope 平行的运行时。

## 设计原则

### 1. Session First

系统的主对象是 `Session`，不是 `Agent`，也不是 `Workspace`。用户驱动的是持续协作线程，而不是单次 run 或某个 agent 的独立调用。

### 2. Team-Driven Collaboration

每个 session 在创建时绑定一个固定 `Team`。第一期不支持 session 运行过程中切换 team。Team 决定：

- 当前主答的 leader agent
- 可调度的 member agents
- 当前协作可用的能力边界

### 3. AgentScope Native Runtime

凡是 AgentScope 已成熟提供的运行时能力，都优先直接纳入系统内核，而不是在外层重写同构机制。包括：

- `Agent.reply_stream(...)`
- `AgentState`
- `ContextConfig`
- `compress_context`
- `observe`
- `RequireUserConfirmEvent / ConfirmResult / UserConfirmResultEvent`
- `Workspace`
- `Toolkit`
- `MessageBus / wakeup / inbox`

### 4. Product Layer Over Runtime Layer

对外暴露的是产品层资源：

- `Session`
- `Team`
- `Workspace`

对内运行时尽量直接贴 AgentScope。产品层和运行时层必须分开，运行时层只做适配，不做替代。

### 5. Local Workspace First

第一期 workspace 策略明确采用本地目录方式：

- 使用本地文件系统
- 不接 Docker
- 不接 E2B
- 不做远程 sandbox

后续如果要接更强隔离环境，应通过 workspace backend 扩展，不推翻产品层对象模型。

## 核心对象模型

### 1. Session

`Session` 是系统绝对中心，表示一条持续协作线程。

一个 session 承载：

- 历史消息
- 当前 team
- 当前绑定 workspace
- 当前 plan 快照
- 当前 summary 快照
- 当前 waiting items 列表
- 当前 agent 状态摘要
- 当前 workspace 状态摘要
- 当前产品层状态

关键规则：

- 一个 session 同时只能有一个 active run
- 允许中途 cancel
- 一个 session 创建后固定绑定一个 team
- 一个 session 创建后固定绑定一个 workspace

### 2. Team

`Team` 在本系统中需要区分为两层：

- **Product Team**：用户可见、可配置的协作模板
- **AgentScope Runtime Team**：AgentScope 内部真实执行 leader/worker 协作链的 team runtime

Product Team 包含：

- 一个 leader agent template
- 若干 member agent templates
- team 级覆盖配置

系统内必须存在一个默认 Product Team。

用户可以：

- 创建 team
- 编辑 team
- 删除 team
- 在创建 session 时被选择绑定

关键修正：

- Product Team 不是最终执行引擎
- 真正的 leader/worker 调度、worker session 创建、回流与 wakeup 由 AgentScope Runtime Team 完成
- backend 的职责是把 Product Team 映射到 Runtime Team，并把 Runtime Team 的状态投影回产品层 session

### 3. AgentTemplate

`AgentTemplate` 是静态 agent 模板，不持有运行态状态。

它负责定义：

- 名称 / 角色
- system prompt
- `default_model_config`
- 默认 tools policy
- 默认 MCP refs
- 默认 skill refs
- 默认 permission policy

关键边界：

- `tools / mcp / skills` 的直接配置归属在 `AgentTemplate`
- `Team` 可以对其做 team-scope override

### 4. Workspace

`Workspace` 是独立产品资源，session 在创建时显式选择并绑定一个 workspace。

它负责：

- 工作目录
- 用户可见名称
- 文件树
- 文件内容
- 执行上下文
- 运行辅助文件

它不负责：

- 定义 tools / mcp / skills 的产品配置归属

关键边界：

- 能力属于 `AgentTemplate / Team`
- 执行目标属于 `Workspace`

### 5. Session Stream

`Session Stream` 不是独立资源组，而是 session 的实时输出通道。

用于输出：

- 大模型流式内容
- tool call / result
- leader / subagent 运行事件
- waiting item 创建/解决
- session 状态变化
- plan 更新
- workspace 变化

## 能力归属边界

### 1. Tools / MCP / Skills

能力归属优先级为：

`AgentTemplate 默认配置 < Team 覆盖配置 < Session 当前运行时实际组装`

具体规则：

- `AgentTemplate` 定义默认可用能力
- `Team` 负责在协作场景中启用、裁剪或覆盖这些能力
- `Runtime` 负责组装最终可用的 toolkit
- `Workspace` 只提供执行目标与工作目录，不承载这类产品配置

### 2. Model Config

不使用模糊的“模型策略”描述。统一采用：

- `default_model_config`

第一期建议至少包含：

- provider
- model
- temperature
- max_tokens

Team 可对此做覆盖。

### 3. Memory / Compression

运行时记忆与压缩直接采用 AgentScope 内核能力：

- `AgentState.context`
- `AgentState.summary`
- `ContextConfig`
- `compress_context`
- offload

产品层只暴露快照，不单独再做 memory 子系统。

### 4. Observe

`observe` 仍然纳入系统，但这里要明确其边界：

- 它属于 AgentScope runtime 内部多 agent 协作能力的一部分
- backend 不单独重写一套 observe 机制
- backend 主要接入 AgentScope 已有的 `TeamCreate / AgentCreate / TeamSay / inbox / wakeup / InboxMiddleware / WakeupDispatcher` 协作链，并将结果投影为产品层状态

它不作为前端一级接口暴露。

### 5. Confirm / Resume

AgentScope 的 confirm/resume 机制直接纳入第一期内核。

产品层体现为：

- session waiting item 列表
- 提交 waiting item 处理结果
- 对应执行链从断点恢复

## waiting_items 设计

`waiting` 采用列表模型而不是单对象模型。

原因：

- leader 可能产生确认请求
- 多个 subagent 也可能分别产生确认请求
- 用户需要逐条处理
- 处理一个 item 后，只恢复对应执行链

### WaitingItem 关键特征

每个 `WaitingItem` 至少应具备：

- `waiting_id`
- `source_type`：leader / subagent
- `source_runtime_id`
- `waiting_kind`：可扩展，不仅限于 `confirm`
- `title`
- `message`
- `payload`
- `status`
- `created_at`
- `updated_at`

### WaitingItem 类型

第一期明确支持扩展，至少考虑：

- `confirm`
- `external_result`

后续如需支持 `question` 等类型，可在不修改整体模型的前提下扩展 `waiting_kind`。

### Session 状态与 waiting_items 的关系

- 只要 `waiting_items` 中存在 `pending` 项，session 就可以呈现 `waiting` 状态
- 用户不能在 waiting 未解除时继续发起新的主消息触发
- 用户可以逐条处理 waiting item
- 某条 waiting item 解决后，只恢复对应执行链

## Team 与 Subagent 运行模型

### 1. 核心纠偏

这一部分必须明确：

- **AgentScope Runtime Team** 是真正的 leader/worker 执行链
- **Product Team** 只是产品层配置与聚合对象
- backend 不再以“自己在 product 层手拼一套 worker orchestration”为目标
- backend 的目标是：**bridge + projection**

也就是说：

- Product Team 决定用户想要的协作模板
- Runtime Team 决定 leader/worker 在 AgentScope 中如何真正运行
- session detail / waiting_items / agent_statuses / session_stream 是对 Runtime Team 执行结果的产品层投影

### 2. AgentScope 已有 team 运行链

AgentScope 的多 agent 协作是会话级并发协作模型，而不是同步子函数调用模型。

已经存在并应优先复用的机制包括：

- `TeamCreate`
- `AgentCreate`
- `TeamSay`
- `TeamDelete`
- `MessageBus.enqueue_wakeup(...)`
- `MessageBus.inbox_push(...)`
- `InboxMiddleware`
- `WakeupDispatcher`

这意味着 worker 调度并不是“概念上支持”，而是 AgentScope runtime 已有完整链路。

### 3. 子任务下发

`AgentCreate` 的真实行为应理解为：

1. 在 AgentScope storage 中创建 worker agent，且 `source="team"`
2. 在 AgentScope storage 中创建该 worker 的独立 session
3. 将首个任务包装为 `HintBlock` 写入 worker inbox
4. 通过 `enqueue_wakeup(...)` 触发 `WakeupDispatcher`
5. `WakeupDispatcher` 对 idle worker session 调用 `ChatService.run(..., input_msg=None)`
6. `InboxMiddleware` 在 worker reasoning 前自动将 leader 任务注入 worker context

因此：

- worker 不需要 backend 再额外发明一套“手动 run 子 session”的机制
- backend 要做的是把 Product Team/session 正确桥接到这条 AgentScope 运行链

### 4. Worker 是否阻塞 Leader

不阻塞。

`AgentCreate` 完成的是“创建并唤醒 worker”，而不是“同步等待 worker 跑完”。

之后 worker 异步独立运行，不同步阻塞 leader 所在主 session。

### 5. Leader 是否继续思考

可以，但不一定。

Leader 在派出 worker 后，后续可能：

- 继续当前轮思考
- 结束当前轮等待回流
- 进入产品层 `waiting` 状态

是否继续推进，由模型与产品层策略共同决定；框架不会强制 leader 必须等待全部 worker 完成。

### 6. Worker 完成后如何回流

worker 完成后，结果通过 AgentScope 现成的 team 消息链回流 leader：

1. worker 通过 `TeamSay` 回报 leader
2. leader inbox 收到消息
3. 系统对 leader enqueue wakeup
4. `WakeupDispatcher` 触发 leader session 新一轮 `ChatService.run(..., input_msg=None)`
5. `InboxMiddleware` 将回流消息以 `HintBlock` 注入 leader 上下文
6. leader 再继续推理、汇总或回复

这里需要补一个在首版设计中未被明确写出的主链完成条件：

- `worker callback -> leader inbox -> wakeup -> InboxMiddleware` 只说明 callback 已被消费
- 它**不自动等价于**产品层已经获得一个稳定可读结果

因此，callback 主链对产品层的完成定义应为：

- worker callback 被 leader 消费后
- 系统必须稳定形成一个可读的 leader assistant hint message
- 该 message 进入 leader session 的 persisted `messages`，作为 callback hint 的权威结果

关键边界：

- `session_stream` 是观察通道，不是 callback 可见性的真源
- replay log 允许被 trim，不能承担 callback 可恢复性的唯一责任
- runtime 内存态中的临时 `HintBlock` 注入，也不能视为产品层已完成

### 7. Worker Session 与主 Session 的关系

worker 有独立 runtime session，但不应暴露成与主 session 平级的前端会话对象。

产品层规则：

- 前端只暴露一个主 session
- worker 作为内部 `subagent runtime` 存在
- 前端通过 `agent_statuses`、`waiting_items` 和 `session stream` 中的 subagent 事件感知它们

### 8. Product Team 与 Runtime Team 的桥接

这是 backend 必须补齐的核心工作：

- session 创建时，依据 Product Team 在 AgentScope storage 中建立 Runtime Team
- leader 主 session 绑定到 Runtime Team
- Product Team 的 `member_agent_ids` 映射到 Runtime Team 的 worker agent/session
- 后续所有 leader->worker->callback 行为都以 Runtime Team 为真执行链

### 9. Worker 是否共享主 Session 上下文

不共享完整 `AgentState`。

worker 继承的是必要任务上下文，例如：

- team charter
- leader 下发的任务说明
- 必要 workspace 背景
- 必要 session 摘要

但不直接共享：

- leader 完整运行态
- 所有未完成工具状态
- 整体完整 session state

## Session 状态机

产品层 session 状态保留：

- `idle`
- `running`
- `waiting`
- `cancelling`
- `failed`

语义如下：

- `idle`：可发送新消息
- `running`：当前主链正在执行
- `waiting`：存在待处理 waiting items 或其他外部输入等待
- `cancelling`：取消请求已发出，正在收口
- `failed`：本轮失败，但 session 仍可继续使用

补充规则：

- 一个 session 同时只能有一个 active run
- 允许 cancel
- cancel 后回到 `idle`
- parent cancel 时级联取消活跃 subagents

## 运行主链

### 1. 创建 Session

创建 session 时同时完成：

- 绑定用户选择的 team
- 绑定用户选择的 workspace
- 初始化 session 状态
- 建立产品层 session 记录
- 建立 leader 对应的 AgentScope runtime session
- 建立 Product Team 对应的 AgentScope Runtime Team
- 建立 worker 对应的 AgentScope runtime agent / runtime session（若 team 含 members）

第一期 `create session` 的请求体建议至少包含：

- `name`
- `team_id`
- `workspace_id`

### 2. 进入 Session 页面

前端应执行：

1. `GET session 详情快照`
2. `GET session stream`

这样页面既能恢复当前快照，也能持续接收后续实时事件。

职责边界：

- `session detail` 负责返回当前可恢复、可稳定读取的聚合视图
- `session stream` 负责后续实时观察，不承担 callback 结果真源职责

### 3. 发送消息

用户在 session 中发送消息时：

- 后端检查 session 当前状态
- 若状态允许，则写入用户消息真源
- 触发该 session 一轮新的运行

### 4. 运行时组装

`runtime_service` 读取：

- 当前 session
- 当前 team
- 当前 leader agent template
- 当前 workspace
- 当前 AgentScope leader session state
- 当前 AgentScope runtime team state
- 当前 AgentScope 相关 message history

并组装 AgentScope runtime，其中：

- leader 主链运行由 leader session 驱动
- worker 协作链由 Runtime Team + wakeup/inbox 机制驱动
- backend 负责把 runtime team 结果投影为产品层聚合视图

### 5. 持续执行

执行阶段通过 AgentScope `reply_stream(...)` 产生持续输出，期间可能发生：

- 文本回复
- tool 调用与结果
- plan 更新
- waiting item 创建
- 通过 `AgentCreate` 创建 worker
- worker 通过 `TeamSay` 回流 leader
- workspace 变化

### 6. 快照更新

运行时同时更新可恢复快照：

- session status
- current plan
- current summary
- waiting items
- agent statuses
- workspace status

这些快照不是只看 leader session，而是以 Runtime Team 为聚合源：

- leader 状态来自 leader runtime session
- worker 状态来自 worker runtime sessions
- worker waiting item 通过 runtime team 聚合后投影为 `source_type=subagent`

补充约束：

- callback hint 的用户可见性不应只依赖 runtime state 快照或 replay event 的临时残留
- 对用户可见的 callback 结果，应以 persisted `messages` 为权威层

### 7. Cancel

用户 cancel 时：

- session 进入 `cancelling`
- 当前 active run 停止推进
- 活跃 subagents 级联取消
- 最终回到 `idle`

## 右侧运行态栏设计

右侧运行态栏采用顶部标签切换，分为 3 个视图：

- `Overview`
- `Runtime`
- `Workspace`

### 1. Overview

展示：

- session 基础信息
- 当前 team 基础信息
- 当前 workspace 基础信息
- session 状态
- leader 与 subagents 的状态摘要

### 2. Runtime

展示：

- `waiting_items[]`
- `current_plan`
- `current_summary`
- 活跃 subagent 状态
- 最近运行事件摘要

### 3. Workspace

展示：

- 文件树
- 文件内容
- 最近变更文件

其中：

- `session 详情` 提供 Overview 与 Runtime 的初始快照
- `session stream` 提供其后续实时更新
- `workspace` 接口提供文件树与文件内容

## 前端与后端的对应关系

### 1. 左侧 Session 栏

来源：

- `列 session`

展示：

- 标题
- 最后更新时间
- 当前状态
- 当前 team 摘要

### 2. 左侧 Workspace 栏

来源：

- `列 workspace`
- `创建 workspace`
- `读文件树`
- `读文件内容`

workspace 是独立资源，用户可先创建，再在创建 session 时选择绑定。

### 3. 左侧 Team 栏

来源：

- `列 team`
- `读 team 详情`

### 4. Session 主页面

来源：

- `读单个 session 所有信息`
- `session stream`

约束：

- callback / hint 的稳定可见性以 persisted `messages` 为准
- `session stream` 负责补充实时过程，不负责定义 callback 最终结果是否存在

展示：

- 历史消息
- 当前 team
- 当前 plan / summary
- 当前 waiting 列表
- 当前 agent 状态
- 当前 workspace 状态

## 对外接口分组

### Session

- 创建 session
- 列 session
- 读单个 session 所有信息
- 发送消息到 session
- 取消 session 当前执行
- 提交某个 waiting item 的处理结果

### Team

- 列 team
- 创建 team
- 更新 team
- 删除 team
- 读单个 team 详情

### Workspace

- 列 workspace
- 创建 workspace
- 更新 workspace 基础信息
- 读文件树
- 读文件内容

### Session Stream

- 订阅某个 session 的实时事件流

不单独保留：

- Runtime 组
- Artifact 组
- 独立 confirm 组

## 服务层划分

第一期服务层划分采用：

- `session_service`
- `session_query_service`
- `runtime_service`
- `workspace_query_service`
- `team_service`
- `team_query_service`

### session_service

处理 session 写动作：

- create
- send message
- switch team
- cancel
- submit waiting item result

### session_query_service

处理 session 读模型：

- list sessions
- get session detail view

该视图会聚合：

- ProductSession 快照
- AgentScope 持久化的消息历史
- 当前 summary / waiting / plan / agent statuses / workspace status

补充要求：

- 对 worker callback / leader hint 这类协作结果，`session_query_service` 读取的是已持久化消息真源
- 不应将 query-time 的临时 event/replay 重建当作长期主语义

### runtime_service

最关键的运行桥接层，负责：

- 组装 AgentScope runtime
- 调用 leader 主链 `reply_stream`
- 维护 Product Team <-> Runtime Team bridge
- 处理状态流转
- 处理 stream 事件
- 处理 confirm / cancel / worker callback / plan / workspace changed

关键修正：

- runtime_service 不再以“自己编排一套 worker 调度器”为目标
- 而是以“接入 AgentScope Runtime Team 并做产品层投影”为目标

### workspace_query_service

处理 workspace 读取：

- list
- file tree
- file content

workspace 的创建与基础信息更新由产品层 `workspace_service` 承担；第一期如不单独拆文件，可先放入现有 workspace 相关应用服务中。

### team_service

处理 team 写动作：

- create
- update
- delete
- init default team

### team_query_service

处理 team 读取：

- list teams
- get team detail

## 模块目录建议

```text
backend/app/
  api/
    router.py
    sessions.py
    session_stream.py
    teams.py
    workspaces.py
    system.py

  services/
    session_service.py
    session_query_service.py
    runtime_service.py
    workspace_service.py
    workspace_query_service.py
    team_service.py
    team_query_service.py

  domain/
    sessions/
      models.py
      schemas.py
    teams/
      models.py
      schemas.py
    workspaces/
      models.py
      schemas.py

  runtime/
    agentscope/
      assembler.py
      chat_runtime.py
      team_runtime.py
      state_runtime.py
      confirm_runtime.py
      workspace_runtime.py

  infrastructure/
    storage/
      session_repository.py
      team_repository.py
      workspace_repository.py
    redis/
      client.py
    workspace/
      manager.py
      file_browser.py
    stream/
      sse.py
```

## 持久化边界

第一期建议以 Redis 为主存储和运行时协调底座。

### Redis 负责

- ProductSession 记录
- Team 记录
- AgentTemplate 记录
- Workspace 记录元信息
- Session 当前状态
- waiting items
- current plan / summary 快照
- AgentScope SessionRecord
- AgentState
- AgentScope 消息历史
- locks / cancel / wakeup / inbox

### Async 生命周期约束

虽然 Redis 是第一期主存储和协调底座，但不能从这里推导出“所有 async 运行时对象都可做 app-scope 共享单例”。

必须明确以下约束：

- background run
- wakeup dispatcher
- request path runtime 调用

不能错误共享跨 event loop 的 async Redis / message bus / scheduler 资源。

也就是说：

- 可以统一创建策略
- 但不能假定所有 runtime 依赖都能安全跨 loop 复用

### 本地 Workspace 文件系统负责

- 工作文件
- 文件树与文件内容
- 运行辅助文件
- offload 文件
- plan 文件真源

第一期不建议额外引入 SQLite 主存储，以避免产品层与运行时层的双写复杂度。

## 与 AgentScope 的兼容性结论

这版架构与 AgentScope 是对齐的，不是对抗的。

产品层我们定义了：

- `Session / Team / Workspace`

运行时层尽量直接复用 AgentScope：

- `Agent`
- `AgentState`
- `reply_stream`
- `ContextConfig / compress_context`
- `observe`
- `RequireUserConfirmEvent / ConfirmResult`
- `Workspace`
- `Toolkit`
- `MessageBus / inbox / wakeup`

只有 AgentScope 没直接提供、但产品必须存在的部分，才由产品层补一层控制壳。

关键适配原则如下：

- 产品层保留 `ProductSessionRecord / TeamRecord / WorkspaceRecord`
- AgentScope 运行时保留 `SessionRecord / AgentState / Msg history`
- 主 session 的 runtime `agent_id` 固定绑定为所选 team 的 `leader_agent_id`
- 产品层不复用 AgentScope 默认的 session/workspace 创建流程，但会在创建 session 时同步创建一条 AgentScope-compatible runtime session 记录
- 消息历史真源直接复用 AgentScope `Msg` 存储
- 运行时压缩只影响 `AgentState.context/summary`，不直接改写产品层历史消息展示

## 非目标

第一期明确不做：

- Docker / E2B workspace backend
- 旧 `agent_service + gateway_service` 双服务结构
- 独立 artifact 资源组
- 独立 runtime 资源组
- 代码 diff 展示
- 自研平行 memory、confirm、observe、tool loop、event bus 机制

## 当前剩余的细化项

本设计的大边界已经确定。仍需后续细化的主要是模型级内容：

- `SessionRecord` 字段结构
- `TeamRecord` 字段结构
- `AgentTemplateRecord` 字段结构
- `WorkspaceRecord` 字段结构
- `WaitingItem` 字段结构
- `agent_statuses` 最小字段集
- stream 事件类型枚举
- Redis key 组织方式

以及必须明确的一项运行语义：

- callback hint 持久化以 `messages` 为权威层，而不是 replay log 或纯 runtime 内存态

仍需在实施前进一步拍板的实现细节只有少数几项：

- workspace 本地根目录规则（推荐 `base_dir/{workspace_id}`）
- workspace 创建时的最小输入字段（至少 `name`，可选 `description`）
- subagent 对 workspace 的使用策略：共享主 workspace、派生子 workspace，还是共享只读+独立写层
- `current_plan_snapshot` 从 workspace 中哪一个 plan 文件路径提取

## 总结

这版后端架构的核心可以压缩为一句话：

- `Session` 是产品主线程
- `Team` 决定当前协作组织
- `AgentTemplate` 定义能力画像
- `Workspace` 决定本地执行目标
- AgentScope 负责实际运行
- `Session Stream` 负责实时输出
- Redis 负责状态与协调

它既保留了你要的产品体验，也最大化吸收了 AgentScope 已有的内核能力。
