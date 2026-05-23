# Agent Loop 设计

## 一、设计目标

这份文档只解决一个核心问题：

- 当 `POST /agent-runs/{run_id}/input` 收到一条输入后，系统应该如何进入对应的 Agent loop，并稳定地推进一次运行实例。

这里的目标不是设计完整的中断、流式事件和复杂调度系统，而是先定义一套最小但清晰的 loop 规范，能够支撑：

- `orchestrator` 处理用户需求、生成和更新计划、发配子任务
- `worker` 处理具体编码任务、直接和用户对话、回传执行结果
- `InputEvent` 统一建模
- `run_id` 驱动统一入口
- `PLAN.md` 由 `plan_tool` 负责同步

## 二、总原则

- `InputEvent` 统一建模
- 只通过 `type + payload` 区分输入语义
- `run_id` 决定进入哪套 loop
- `AgentRun.agent_kind` 决定是 `orchestrator` 还是 `worker`
- `worker` 也可以直接和用户对话
- `worker` 只能写代码，不能发配子任务
- loop 本身只负责推进控制流，不直接承担业务实现
- 所有关键状态变化都必须回写到 `AgentRun / InputEvent / Plan / Subtask`

## 三、统一输入入口

整体链路如下：

```text
POST /agent-runs/{run_id}/input
-> validate
-> persist InputEvent(type + payload)
-> load AgentRun by run_id
-> resolve agent_kind
-> enter orchestrator loop or worker loop
-> tool call
-> update state / PLAN.md
-> return accepted
```

这里的关键点是：

- `type` 不负责决定进入哪套 loop
- 真正的分流发生在 `run_id -> AgentRun -> agent_kind`
- `InputEvent.type` 只负责表达“这次输入是什么语义”

例如：

- `user_input`
- `worker_callback`
- 后续也可以继续扩展 `question_reply`、`system_event`

## 四、Loop 的统一控制结果

Agent loop 每一轮结束后，不应该返回零散布尔值，而应统一收敛成三种控制结果：

- `continue`
- `wait`
- `stop`

这是整个 loop 设计里最重要的约束。

### 1. `continue`

表示：

- 当前 run 不需要等待外部输入
- 可以立刻继续下一轮内部 loop
- 通常出现在：
  - 模型刚执行完一个 tool call，还需要继续推理
  - 当前轮只是更新了内部状态，还没有走到稳定停点

`continue` 不代表“用户决定继续”，而是：

- **当前这轮 loop 根据自身状态判断，还应该继续推进**

也就是说，`continue / wait / stop` 是 loop 在每轮结束时产生的控制结果，不是用户手动写进去的状态。

### 2. `wait`

表示：

- 当前 run 已经推进到一个稳定停点
- 但任务还没有结束
- 需要等待下一次外部输入后，才能继续下一轮 loop

`wait` 可以同时覆盖两类场景：

- 等待用户确认
- 等待子任务完成后回调

所以 `wait` 是一个统一的“暂停并等待新事件”的状态。

`wait` 状态下，本轮对话会结束，HTTP 请求也会返回；后续只有新的 `InputEvent` 到来，才会重新进入 loop。

### 3. `stop`

表示：

- 当前 run 本轮目标已经结束
- 不需要继续等待下一次输入来推进当前流程

例如：

- 用户问题已经回答完成
- `worker` 任务已完成，并已经产出回调结果
- `orchestrator` 已确认本轮计划执行结束

## 五、为什么需要 `wait`

如果只有 `continue` 和 `stop` 两种状态，会有一个明显问题：

- 有很多场景不是“继续跑到底”
- 也不是“任务已经结束”
- 而是“当前先停住，等下一个事件”

典型就是：

- `question_tool` 发出提问后，等待用户选择
- `delegate_tool` 发出子任务后，等待 `worker_callback`

所以：

- `continue` = 立即继续内部循环
- `wait` = 结束本轮请求，等待外部事件
- `stop` = 当前 run 完成

## 六、参考 opencode 的设计

`opencode` 最值得参考的，不是它的复杂事件系统，而是它的 loop 组织方式。

### 1. 单点主循环

`opencode` 在 [prompt.ts](file:///e:/Github/AI项目调研/opencode/packages/opencode/src/session/prompt.ts#L1240-L1316) 中定义了明确的 `runLoop()`，并通过一个 `while (true)` 持续推进 session。

这说明一个非常重要的规范：

- loop 必须有一个明确的单点入口
- 不要把“继续下一轮”的逻辑散落在多个 service 和 tool 中

对当前方案来说，对应的设计应是：

- `run_orchestrator_loop(run_id, event_id)`
- `run_worker_loop(run_id, event_id)`

### 2. 每轮先读状态，再决定下一步

`opencode` 的主循环每轮都会：

- 重新读取当前 session 消息
- 找到最新 user / assistant / task 状态
- 再决定是否退出、是否处理 subtask、是否继续模型调用

这对应到当前设计里，应当变成：

- 读取 `AgentRun`
- 读取最新 `InputEvent`
- 读取当前 `Plan`
- 读取相关 `Subtask`
- 再进入当前轮推理

也就是说：

- loop 不应该只信进程内临时变量
- 每轮都应以持久状态为准

### 3. loop 只返回有限动作

`opencode` 的 `SessionProcessor.process()` 会把一轮处理结果收敛成少数几种结果，例如：

- `continue`
- `stop`
- `compact`

这很值得参考。

当前方案虽然先不做 compaction，但同样应该坚持：

- 一轮 loop 最终只返回有限动作

所以本方案将其收敛为：

- `continue`
- `wait`
- `stop`

### 4. tool 执行和 loop 决策分离

`opencode` 把：

- 模型调用
- tool call 处理
- tool result 回写
- loop 决策

拆成不同层级，而不是全塞在一个大函数里。

对当前方案来说，也应保持同样原则：

- `ToolExecutor` 负责执行工具
- loop 负责决定下一步是 `continue / wait / stop`

## 七、参考 Hermes 的设计

Hermes 最值得参考的，不是它的中断机制，而是它的“手写 tool loop”方式。

### 1. 典型工具循环

在 [conversation_loop.py](file:///e:/Github/AI项目调研/hermes-agent-src/agent/conversation_loop.py#L532-L557) 中，Hermes 明确使用一个手写 `while` 循环来做：

- 调模型
- 检查是否有工具调用
- 执行工具
- 把工具结果回写消息历史
- 再进入下一轮

这说明：

- 你的 loop 完全可以不依赖 `LangChain Agent`
- 自己手写一个定制化 loop 是合理且可控的

### 2. 工具循环的最小形态

Hermes 的核心思路可以抽象成：

```text
assemble context
-> call model
-> if tool call:
     execute tool
     append tool result
     continue
-> else:
     finalize response
```

这一点对当前方案特别有用，因为你的 `orchestrator loop` 和 `worker loop` 本质上也都需要这样一个最小工具循环。

### 3. 继续与结束的判断由 loop 自身负责

Hermes 不需要用户每一步都明确说“继续”，而是 loop 自己根据当前输出判断：

- 还有工具要执行就继续
- 没有工具、内容已完整就结束

这对应到当前方案里就是：

- `continue / wait / stop` 由 loop 在每轮结束时自己给出
- 用户只是通过新的输入事件重新唤醒下一轮

## 八、当前方案的 Loop 规范

### 1. 通用 loop 规范

无论是 `orchestrator` 还是 `worker`，都遵循统一流程：

```text
load run state
-> load latest InputEvent
-> assemble runtime context
-> select toolset by agent_kind
-> call model
-> if tool call:
     execute tool
     persist tool result
     continue
-> if final response:
     decide continue / wait / stop
-> persist run state
-> return loop result
```

### 2. `LoopResult` 不是模型输出，而是 runtime 判定结果

`continue / wait / stop` 不应被设计成让模型在提示词里显式输出：

- `"continue"`
- `"wait"`
- `"stop"`

更合理的方式是：

- 模型只负责正常回复、调用工具、发起提问、发配任务、产出最终结果
- runtime 在每轮末尾根据本轮已经发生的事实，计算出 `LoopResult`

这点同时参考了：

- `opencode` 的 `processor -> continue/stop/compact`
- Hermes 的“是否还有 tool call / 是否已经形成 final response”判断

也就是说：

- **控制结果由 loop 计算**
- **不是由模型声明**

### 3. `LoopResult` 的统一判定规则

建议在每轮 loop 末尾按固定顺序判断：

1. 如果本轮调用了 `question_tool`
   - 返回 `wait`
   - 原因：当前 run 需要等待用户回答
2. 如果本轮调用了 `delegate_tool`
   - 返回 `wait`
   - 原因：当前 run 需要等待 `worker_callback`
3. 如果本轮出现不可恢复错误
   - 返回 `stop`
   - 原因：当前 run 不能继续自动推进
4. 如果本轮已经形成最终回复，且没有待处理 tool call
   - 返回 `stop`
   - 原因：当前 run 本轮已经完成
5. 如果本轮执行了 tool，且还需要继续推理或继续执行
   - 返回 `continue`
6. 如果以上都不满足，但当前仍未达到稳定停点
   - 返回 `continue`

可以把它抽象成：

```text
if question emitted:
  return wait

if delegate emitted:
  return wait

if fatal error:
  return stop

if final response and no pending tool call:
  return stop

return continue
```

### 4. 为什么“最终回复”会触发 `stop`

这里的“最终回复”不是模型输出一个文本 `"stop"`，而是：

- 当前 assistant/message 已经形成完整自然语言回复
- 没有新的 tool call
- 没有 question/delegate 等待中的外部动作
- 当前 run 的本轮目标已经满足

这和 `opencode` 外层 `runLoop()` 的退出逻辑一致：

- 不是靠模型说“我要停了”
- 而是 runtime 看到“当前 assistant 已经完成，且不再需要工具”，于是跳出循环

### 5. `wait` 与对话结束的关系

`wait` 表示：

- 当前 HTTP 请求结束
- 当前这一轮 loop 结束
- 当前对话不会继续在同一次请求里自动往下跑

但 `wait` 不表示任务完成，只表示：

- 当前 run 需要等待下一次外部输入

因此：

- `continue`：同一次请求内继续推进
- `wait`：结束本次请求，等下一个 `InputEvent`
- `stop`：当前 run 结束

### 6. `orchestrator loop`

职责：

- 接用户输入
- 聊天澄清需求
- 生成或更新计划
- 触发 `question_tool`
- 触发 `delegate_tool`
- 回收 `worker_callback`
- 决定下一步是继续、等待还是结束

规则：

- 不直接承担业务执行
- 不直接写代码
- 可以调用：
  - `plan_tool`
  - `question_tool`
  - `delegate_tool`

推荐控制流：

```text
InputEvent -> load Plan / Run / Subtasks
-> assemble orchestrator prompt
-> call model
-> if question_tool:
     emit question
     return wait
-> if delegate_tool:
     create subtask
     return wait
-> if only internal planning/tool updates:
     return continue
-> if goal reached:
     return stop
```

### 7. `worker loop`

职责：

- 接用户输入
- 执行代码任务
- 修改文件、跑测试、输出结果
- 直接回答、解释、补充

规则：

- 能聊天
- 能写代码
- 不能发配子任务
- 不能调用 `delegate_tool`
- 不维护全局 `Plan`

推荐控制流：

```text
InputEvent -> load task context / run state
-> assemble worker prompt
-> call model
-> if code tool call:
     execute code tool
     return continue
-> if task completed:
     build worker_callback payload
     return stop
-> if still needs local execution:
     return continue
```

## 九、提示词设计

### 1. 不使用显式 ReAct 模板

当前方案不建议在主提示词中要求模型显式输出：

- `Thought:`
- `Action:`
- `Observation:`

也不建议让模型在结尾输出：

- `"continue"`
- `"wait"`
- `"stop"`

更适合的方式是参考 `opencode` 和 Hermes：

- 提示词只约束角色、工具边界、行为方式和输出要求
- runtime 根据模型是否调用工具、是否已经形成最终回复，来决定 loop 控制结果

### 2. 参考 opencode 的 prompt 组装方式

`opencode` 的主提示词不是一份固定大 prompt，而是运行时拼装出来的。

可以概括成：

```text
system prompt
= provider/model prompt
+ environment prompt
+ instruction prompt
+ skills prompt
+ mode prompt
```

然后再加上：

- message history
- tool schemas

这种方式很值得参考，因为它天然适合：

- `orchestrator` 和 `worker` 分开配置
- 不同模型使用不同 provider prompt
- 不同 Agent 使用不同 skill prompt

### 3. 当前方案的 prompt 分层

建议把 prompt 拆成下面几层：

#### `provider prompt`

负责：

- 按模型或框架定义基础行为规范
- 例如：
  - Claude 风格提示词
  - GPT/Codex 风格提示词

这一层更像 `opencode` 的：

- `anthropic.txt`
- `gpt.txt`
- `codex.txt`

#### `environment prompt`

负责注入运行环境：

- 当前工作目录
- 当前 workspace
- 当前平台
- 是否 git repo
- 当前日期
- 当前 run_id
- 当前 agent_kind

#### `instruction prompt`

负责注入当前系统级业务规则，例如：

- AgentHub 的产品边界
- 单聊 / 群聊规则
- Workspace / Proposal / Plan 的使用规则

#### `skills prompt`

负责注入当前 Agent 具备的 skill 描述。

例如：

- `task_breakdown`
- `code_review`
- `api_design`
- `requirement_analysis`

#### `mode prompt`

负责注入当前运行模式约束。

例如：

- `orchestrator mode`
- `worker mode`
- 后续也可以扩展：
  - `plan_only mode`
  - `review mode`

### 4. `orchestrator prompt` 的核心要求

`orchestrator prompt` 应重点约束：

- 负责澄清需求
- 负责生成和更新计划
- 必要时调用 `question_tool`
- 必要时调用 `delegate_tool`
- 不直接承担业务实现
- 不直接写代码
- 收到 `worker_callback` 后要判断下一步

可概括为：

```text
You are the orchestrator.
You are responsible for clarifying user intent, maintaining the plan, delegating subtasks, and deciding what happens next.
Do not directly implement business logic or code changes.
Use question_tool when user confirmation or clarification is required.
Use delegate_tool when a concrete subtask should be assigned to a worker.
Use plan_tool to create or update the plan.
```

### 5. `worker prompt` 的核心要求

`worker prompt` 应重点约束：

- 负责具体任务执行
- 可以和用户直接对话
- 可以读写代码、跑测试、解释实现
- 不能调用 `delegate_tool`
- 不维护全局 `Plan`
- 完成时要产出可回传的结果

可概括为：

```text
You are a worker agent.
You can execute concrete implementation tasks and talk directly with the user.
You may use coding tools to read, edit, run, and verify code.
You must not delegate subtasks.
You do not maintain the global plan.
When your task is done, produce a final task result that can be sent back to the orchestrator.
```

### 6. prompt 与 loop 的职责边界

需要明确区分：

- prompt 负责约束模型“怎么做”
- loop 负责决定系统“下一步怎么走”

也就是说：

- prompt 决定：
  - 能不能调用某个 tool
  - 什么情况下该提问
  - 什么情况下该发子任务
- loop 决定：
  - 本轮是 `continue`
  - 还是 `wait`
  - 还是 `stop`

这条边界必须稳定，否则后面很容易把系统控制流写进 prompt，导致逻辑难维护。

## 十、InputEvent 与 run_id 的职责边界

### 1. `InputEvent.type`

作用：

- 不负责分流到两套 schema
- 只负责表达这次输入语义

例如：

- `user_input`
- `worker_callback`

### 2. `run_id`

作用：

- 定位当前 run
- 由 `AgentRun.agent_kind` 决定这次走 `orchestrator` 还是 `worker` loop

所以真正的分流链路是：

```text
run_id
-> AgentRun
-> agent_kind
-> orchestrator loop or worker loop
```

而不是：

```text
type -> loop
```

## 十一、PLAN.md 的归属

`PLAN.md` 不属于 `run_input` 接口层。

它的归属应是：

- `plan_tool` 负责更新内存里的 `Plan`
- `plan_tool` 负责同步写入 `PLAN.md`

因此：

- `run_input` 只负责把输入送到正确的 loop
- loop 只负责决定是否调用 `plan_tool`
- `plan_tool` 负责最终的计划状态更新和文件同步

## 十二、文件级结构

```text
app/
├─ api/
│  └─ agent_run_input.py
├─ schemas/
│  └─ agent_run_input.py
├─ services/
│  └─ agent_run_input_service.py
├─ runtime/
│  ├─ runtime_resolver.py
│  ├─ loop_base.py
│  ├─ orchestrator_loop.py
│  └─ worker_loop.py
└─ tools/
   ├─ plan_tool.py
   ├─ question_tool.py
   ├─ delegate_tool.py
   └─ code_tool.py
```

### 1. `app/api/agent_run_input.py`

- 只接收 `run_id`
- 接收统一 `InputEvent` 请求
- 同步返回 `accepted`
- 业务错误返回 `4xx`

### 2. `app/schemas/agent_run_input.py`

- 一个外层 `InputEventRequest`
- 一个统一 `InputEvent`
- 不拆平行 schema
- `payload` 承载具体内容

### 3. `app/services/agent_run_input_service.py`

- 幂等检查
- 写入 `InputEvent`
- 读取 `AgentRun`
- 根据 `run.agent_kind` 选择 loop
- 推进状态

### 4. `app/runtime/`

- `runtime_resolver.py`：按 `run_id` 解析 `agent_kind`
- `loop_base.py`：定义通用 `LoopResult`
- `orchestrator_loop.py`：主控 loop
- `worker_loop.py`：执行 loop

### 5. `app/tools/`

- `plan_tool`
- `question_tool`
- `delegate_tool`
- `code_tool`

## 十三、建议的最小实现顺序

1. 统一 `InputEvent` 模型
2. `agent_run_input` 接口只接一个入口
3. `AgentRunInputService` 做幂等和落库
4. `RuntimeResolver` 按 `run_id` 找 `agent_kind`
5. 实现 `LoopResult = continue | wait | stop`
6. 先把 `LoopResult` 判定规则写死在 runtime
7. 分层实现 `provider/environment/instruction/skills/mode` prompt
8. 两套 loop 先只做状态流转
9. `plan_tool` 接上 `PLAN.md` 同步
10. 再逐步补 question、delegate、worker callback

## 十四、一句话总结

这套 `Agent loop` 设计参考了 `opencode` 的“单点主循环 + 有限控制结果”规范，以及 Hermes 的“手写 tool loop”方式：统一从 `POST /agent-runs/{run_id}/input` 进入，依赖 `run_id -> AgentRun -> agent_kind` 分流到 `orchestrator` 或 `worker` loop，并在每轮结束后只返回 `continue / wait / stop` 三种结果，从而稳定支撑动态计划、用户确认和子任务回调。
