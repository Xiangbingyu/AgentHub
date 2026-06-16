# Backend Runtime Mainline Hardening Design

## 概述

本设计聚焦 `backend/` 当前第一阶段主链中的 4 个真实缺口，并只处理这一条运行时主链，不混入 Team worker/subagent 深化、生命周期重构或更大范围工程治理。

本轮目标是把以下能力从“可用初版”收口到“前后端可以稳定依赖”的状态：

- `send_message` 从“注册后台 task 但仍 await 完整执行”改为真正的立即返回异步执行
- `session_stream` 从“能连通”提升为“可验证 replay/live/terminal 事件”的稳定实时通道
- `cancel` 从“状态和广播已接上”提升为“可证明能打断后台长任务并正确收口状态”
- `waiting_items` 从“最后一条消息的首版投影”提升为“按运行时上下文聚合、去重、保留本地处理结果”的稳定投影

## 范围

### 本轮纳入

- `POST /api/v1/sessions/{session_id}/messages` 的最终语义收口
- runtime 后台 run 生命周期收口
- `POST /api/v1/sessions/{session_id}/cancel` 的真实中断行为收口
- `GET /api/v1/sessions/{session_id}/stream` 的事件语义与测试增强
- `waiting_items` 的提取、去重、状态保留与恢复路径增强
- 上述行为对应的 service/API/SSE 测试

### 本轮明确不纳入

- Team worker / subagent 的真实多 agent 调度链
- `agent_statuses` 的完整实时状态体系
- `@app.on_event(...)` 到 lifespan 的迁移
- `user_id` 来源治理
- 更大范围的依赖注入、单例生命周期、日志/追踪、错误模型统一

这些能力后续可以在主链稳定后继续做，但不与本轮耦合实现。

## 问题确认

### 1. `send_message` 不是最终异步形态

当前 `backend/app/services/runtime_service.py` 中，`send_message(...)` 会通过 registry `spawn(...)` 注册后台 task，但随后仍然 `await task`。这意味着：

- HTTP 虽返回 `202`，但服务端语义仍接近同步执行
- 一次长运行会阻塞请求生命周期
- `cancel` 和 `stream` 的时序验证不够真实

### 2. `session_stream` 测试只覆盖了连通性

当前测试能证明 SSE 能建立连接，但不能证明：

- replay 事件可被读取
- live 事件会在后台 run 执行时持续到达
- cancel 或 waiting 产生的状态变化会作为 terminal/live 事件出现

### 3. `cancel` 还没有证明真正中断后台任务

当前实现会：

- 将 product session 写为 `cancelling`
- 取消 registry 中的本地 task
- 通过 AgentScope bus 发布 cancel

但缺少一个可控的慢任务执行路径来证明：

- 后台 task 被真正打断，而不是自然执行完成
- product session 最终状态能从 `cancelling` 收口到稳定终态

### 4. `waiting_items` 只用了首版末消息投影

当前仅扫描 runtime context 的最后一条消息中的 `tool_call` block，存在以下限制：

- 无法稳定处理多个 waiting item
- 不能从更完整的上下文中恢复 waiting 状态
- 已在产品层被用户处理的 `resolved/rejected` 结果，容易被后续 runtime 快照覆盖

## 设计原则

### 1. 仍以 Product Session 为外部真源

前端和 HTTP API 继续以产品层 session 聚合视图为契约：

- session status
- waiting items
- summary snapshot
- plan snapshot
- session detail messages

AgentScope runtime 继续作为内核运行真源，但不会直接取代产品层聚合接口。

### 2. 立即返回只保证“已入队并已启动后台 run”

`send_message` 返回时，不保证 assistant reply 已产生；只保证：

- session 存在且允许新输入
- user message 已成功送入 runtime 执行链
- 本次 run 已被后台 registry 接管
- 运行状态已切换为 `running`

后续结果全部通过 session detail 轮询或 `session_stream` 观察。

### 3. 状态收口必须由单一路径完成

后台 run 在结束、取消、失败、等待时，需要由一个统一同步逻辑完成以下投影：

- `current_summary_snapshot`
- `waiting_items`
- `session.status`

避免多个调用点分别写状态，造成时序覆盖。

### 4. cancel 采用“本地 task 中断 + runtime 广播 + 关键边界检查”三层策略

仅广播不够，仅 `task.cancel()` 也不够。本轮采用三层中断策略：

- Product session 标记 `cancelling`
- Registry 中运行中的 asyncio task 立即取消
- runtime 关键边界再次读取 session 状态并尽快收口

这样即使底层 runtime 不能瞬间停止，也能保证上层状态不会继续误判为正常完成。

## 目标行为

### 1. `send_message`

请求 `POST /api/v1/sessions/{session_id}/messages` 的最终行为：

1. 读取 `ProductSessionRecord`
2. 校验 session 状态必须允许新消息进入
3. 将 session 状态切为 `running`
4. 创建后台 task，并交给 `ChatRunRegistry`
5. 立即返回 `202 Accepted`

后台 task 自身负责：

- 调用 `AgentScopeChatRuntime.run_user_message(...)`
- 在 finally/except 分支中统一回填 summary / waiting / terminal status
- 必要时发布状态变化事件供 stream 读取

### 2. runtime run 生命周期

本轮不额外引入独立数据库 job 表，但在内存 registry + product status 上形成清晰语义：

- `idle`
- `running`
- `waiting`
- `cancelling`
- `failed`
- `idle`（正常完成后的收口状态）

本轮不额外新增 `completed` 或 `cancelled` 的持久化 session status，以避免扩大前端兼容面；取消后的收口仍回到 `idle`，但必须确保中间的 `cancelling` 和 stream terminal 事件可见。

### 3. `cancel`

`POST /api/v1/sessions/{session_id}/cancel` 的行为：

1. 读取 session
2. 写入 `status = "cancelling"`
3. 尝试取消 registry 中运行 task
4. 发布 runtime cancel 广播
5. 后台 task 在取消异常或边界检查中进入统一收口逻辑

收口规则：

- 若 session 已处于 `cancelling` 且 runtime 未产生新的 waiting，则最终写回 `idle`
- 不把被用户处理过的 waiting item 状态重置回 `pending`
- 若 runtime 在取消前已进入 waiting，则保留 waiting 状态

### 4. `waiting_items`

waiting 投影逻辑从“最后一条消息”提升为“遍历当前 runtime context 中所有 assistant message 的 tool_call block”。

提取策略：

- 仅提取 `state in {"asking", "submitted"}` 的 block
- 使用 `tool_call.id` 作为 `waiting_id`
- 若同一 `waiting_id` 在上下文中多次出现，以最后一次状态为准
- 将已存在于 product session 中的 `resolved/rejected` 状态合并回新投影结果，避免被 runtime 新快照覆盖

这样可以稳定支持：

- 一个 session 同时存在多个 waiting item
- confirm / external_result 两种首期 waiting 类型
- 用户先处理、runtime 后回读时的状态保留

### 5. `session_stream`

当前 stream 继续保持：

- 首帧 `session.ready`
- 历史 replay
- live subscribe
- 心跳注释帧

但本轮要求通过测试明确验证：

- 连接建立后能收到 `session.ready`
- 发送消息后，stream 能收到至少一个 live session event
- 产生 waiting 时，stream 能收到与 waiting 相关的 live event 或状态事件
- cancel 后，stream 能观察到状态变化或 terminal event

这里不强制改变所有事件格式；重点是让事件语义可观测、可测试、与产品层状态收口一致。

## 组件改动

### 1. `backend/app/services/runtime_service.py`

职责调整为：

- `send_message(...)` 只做校验、写 `running`、注册后台任务、立即返回
- 新增内部统一收口逻辑，例如 `_sync_runtime_state(...)`
- 新增 cancel 边界判断辅助逻辑
- 重写 waiting 提取逻辑，支持全上下文扫描与状态合并

关键要求：

- 不在 `send_message(...)` 中等待后台任务完成
- task 自己处理成功、失败、取消三种退出路径
- 在任务退出前统一做一次 product session 状态回填

### 2. `backend/app/api/sessions.py`

若当前已经返回 `202`，保持该状态码不变；但要确保 API 实际语义与之匹配，即 handler 不等待完整运行完成。

### 3. `backend/app/api/session_stream.py`

主实现可保持现有结构，但允许根据测试需要做小幅增强，例如：

- 让 replay/live 事件的读取更稳定
- 明确断开时的 feeder task 清理路径
- 在测试场景下能稳定观察首帧和后续 live 帧

### 4. `backend/tests/test_runtime_service.py`

新增或重写以下类型测试：

- `send_message` 注册后台任务后立即返回，而不是等待慢 runtime 完成
- `cancel` 会中断慢 runtime task，并最终让 session 离开 `cancelling`
- waiting 提取会扫描完整上下文并支持多 item
- waiting 合并会保留本地 `resolved/rejected` 状态

### 5. `backend/tests/test_session_api.py`

新增 API 级行为测试：

- `POST /messages` 立即返回 `202`
- 后台 run 稍后把 assistant message 写入 session detail
- cancel 在慢任务上能触发状态变化

### 6. `backend/tests/test_session_stream.py` 或现有 `test_session_api.py`

建议将 stream 测试拆出独立文件，以减少 API 主链测试文件的职责混杂。

新增测试覆盖：

- `session.ready` 首帧
- 历史 replay 可读
- live event 在发送消息后可读
- cancel 或 waiting 相关事件可观测

## 测试设计

### 1. TDD 顺序

严格采用以下顺序：

1. 先写 `RuntimeService` 级失败测试
2. 跑单测，确认当前实现失败原因符合预期
3. 最小修改 `runtime_service.py`
4. 再补 API 级失败测试
5. 再补 SSE 级失败测试
6. 所有测试通过后再做轻量整理

### 2. 取消测试策略

为避免依赖真实 LLM 时序，本轮通过可控 fake runtime 或 slow async stub 构造长任务：

- slow runtime 在执行期间等待一个 asyncio event 或 sleep
- cancel 后断言 task 被取消或 run 提前退出
- 最终断言 session status 从 `cancelling` 收口为 `idle` 或 `waiting`

### 3. SSE 测试策略

优先使用当前测试栈能稳定支持的方式，不追求复杂的全异步端到端框架切换。

目标是保证：

- 能读到 SSE 首帧
- 能在另一个触发动作后读到至少一个 live 事件
- 不依赖任意长时间睡眠，而是采用条件轮询或小范围等待

## 风险与取舍

### 1. 仍是单进程 registry

本轮仍依赖 `ChatRunRegistry` 保存本进程后台任务。这不是最终的多实例方案，但对当前本地 backend 与测试目标足够。

### 2. session 终态继续复用 `idle`

本轮不新增 `cancelled/completed` 持久化状态，减少兼容面。但这也意味着前端若要区分“正常结束”和“取消结束”，需要依赖 stream terminal event 或未来扩展字段。

### 3. stream 事件格式本轮不做大重构

本轮重点是“可观测且可测”，而不是重新定义完整事件协议。若后续前端要更细粒度的 runtime event taxonomy，可以在主链稳定后独立推进。

## 验收标准

满足以下条件即认为本轮主链收口完成：

- `send_message` 不再等待后台 run 完整结束才返回
- 慢 runtime 测试能证明 cancel 会打断后台任务
- waiting 投影支持多 item、去重和本地状态保留
- session stream 测试覆盖首帧、replay/live 至少一类状态变化事件
- 相关 pytest 通过，且不依赖真实外部 LLM 才能验证这些行为
