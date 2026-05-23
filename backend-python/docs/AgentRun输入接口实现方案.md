# `POST /agent-runs/{run_id}/input` 实现方案

## 1. 接口定位

这个接口不是普通的消息写入接口，而是 **AgentRun 的统一输入入口**。

在这个输入接口之外，还需要一个创建运行实例的接口：`POST /agent-runs`。

它的职责是：

- 接收用户输入
- 接收 worker 回调结果
- 触发对应 Agent 的循环执行
- 驱动对应 Agent 继续 `plan -> delegate -> 回收 -> 下一步`

一句话：**它是 Agent loop 的启动点和续跑点。**

---

## 2. 核心思路

系统里只有一条主链路：

```text
input -> AgentRun -> Agent loop -> tool call -> output -> 下一轮 input
```

但这条链路里的 Agent 可以分两类：

- `orchestrator`：主 Agent，负责对话、规划、分发、回收
- `worker`：子 Agent，负责执行具体任务

它们都可以使用同一个 `POST /agent-runs/{run_id}/input`，区别只在于：

- `run_id` 指向的是哪一种运行实例
- 这个 `run` 允许使用的工具集
- 这个 `run` 的下一步动作

因此最小对外接口应当只有两个：

- `POST /agent-runs`：创建一次运行实例，返回 `run_id`
- `POST /agent-runs/{run_id}/input`：向指定运行实例投递输入，触发 loop

---

## 3. 两个核心接口

### 3.1 `POST /agent-runs`

这个接口只负责创建一个新的 `AgentRun`，不负责执行首轮对话。

建议请求体：

```json
{
  "agent_id": "uuid",
  "workspace_id": "uuid",
  "metadata": {}
}
```

字段说明：

- `agent_id`：必填，明确指定本次运行的具体 Agent
- `workspace_id`：必填，指定当前运行绑定的 Workspace
- `metadata`：可选，预留业务侧附加信息

这里不建议让前端直接传 `agent_kind`，因为：

- 前端更应该选择“具体 Agent”而不是“Agent 类型”
- `agent_kind` 应由后端根据 `agent_id` 的配置自动推导
- 同一个接口既服务主 Agent，也服务普通 Agent，不需要前端显式区分两套类型

建议响应体：

```json
{
  "run_id": "uuid",
  "agent_id": "uuid",
  "status": "created"
}
```

### 3.2 `POST /agent-runs/{run_id}/input`

这个接口只负责向一个已存在的 `run` 投递输入，并触发该 `run` 的 loop。

建议请求体：

```json
{
  "input_id": "uuid",
  "source_type": "user",
  "content": "请帮我实现登录接口",
  "idempotency_key": "uuid"
}
```

最小字段说明：

- `input_id`：输入事件 ID，用于追踪
- `source_type`：输入来源，例如 `user`、`worker`、`system`
- `content`：本次输入内容
- `idempotency_key`：幂等键，避免重复执行

worker 回调时也走同一个接口，只是 `source_type=worker`，`content` 变成子任务结果摘要。

建议响应体：

```json
{
  "run_id": "uuid",
  "status": "accepted"
}
```

### 3.3 模块拆分建议

这两个接口建议拆到两个独立模块中，分别维护：

- `POST /agent-runs`：创建运行实例模块
- `POST /agent-runs/{run_id}/input`：运行输入与 loop 驱动模块

推荐目录结构：

```text
app/
├─ api/
│  ├─ agent_run_create.py
│  └─ agent_run_input.py
├─ schemas/
│  ├─ agent_run_create.py
│  └─ agent_run_input.py
├─ services/
│  ├─ agent_run_create_service.py
│  └─ agent_run_input_service.py
├─ repositories/
│  ├─ agent_run_repository.py
│  └─ input_event_repository.py
└─ models/
   ├─ agent_run.py
   ├─ input_event.py
   └─ subtask.py
```

模块职责边界：

- `agent_run_create` 模块只负责创建 `AgentRun`
- `agent_run_input` 模块只负责向既有 `AgentRun` 投递输入并驱动 loop
- 两个模块在接口层、schema 层、service 入口层保持分离
- 两个模块在底层共享 `AgentRun`、`InputEvent`、`Subtask` 这套运行实体

这里不建议做成“完全互不关联”的两套系统，原因是：

- `input` 模块本质上必须依赖 `run` 的存在
- worker 回调必须回到已有的主 run
- run 状态、子任务关系、幂等记录都需要共享同一个主键体系

因此更合理的原则是：

- 路由分开
- service 入口分开
- schema 分开
- 数据实体共享

一句话：**接口模块分开，运行主线不断开。**

---

## 4. 运行结构

```text
            ┌───────────────────────────────┐
            │ POST /agent-runs/{run_id}/input │
            └─────────────┬─────────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │ Load AgentRun   │
                │ + context       │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Select Agent     │
                │ orchestrator/worker
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Run agent loop   │
                └────────┬────────┘
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
      主 Agent 回复            Worker 执行任务
             │                       │
             │                       ▼
             │              产出结果并回调主 run
             │                       │
             └───────────────◄───────┘
```

---

## 5. 主流程

### 5.1 用户唤醒主 Agent

用户在群聊或单聊里 `@Orchestrator` 后，前端把输入送到这个接口。

后端做的事：

- 记录本次输入
- 读取 `PLAN.md` 或当前计划状态
- 唤醒主 Agent
- 进入主 Agent 循环

主 Agent 会不断做这些事：

- 读取用户输入
- 结合上下文继续对话
- 判断是否信息已足够
- 生成 `plan`
- 等待用户确认

### 5.2 用户确认 plan

确认后，主 Agent 才可以调用 `delegate_tool`。

此时主 Agent 不再继续“自己做完所有事”，而是：

- 将 plan 中的某一步分派给 worker
- worker 独立执行
- worker 完成后把结果回传给主 run

### 5.3 worker 完成后回调

worker 结束任务后，不继续留在自己的执行上下文里处理业务，而是：

- 把结果作为新的 input
- 投递回对应的主 run
- 重新唤醒主 Agent

主 Agent 收到后会：

- 更新 `PLAN.md`
- 检查下一步
- 决定继续 `delegate` 还是结束本轮

---

## 6. 两类 Agent 的区别

### 6.1 主 Agent

主 Agent 拥有：

- `plan_tool`
- `question_tool`
- `delegate_tool`

它的职责是：

- 和用户一直聊到需求确认
- 生成和维护计划
- 分配任务给子 Agent
- 回收子 Agent 结果
- 推进下一步

### 6.2 Worker Agent

Worker 拥有：

- 自己的业务工具，例如 `code_tool`

它的职责是：

- 执行单个任务
- 写代码 / 改文件 / 跑测试
- 输出结果
- 主动回调主 run

Worker **不应该** 再拥有 `delegate_tool`，否则就容易形成嵌套调度。

---

## 7. 推荐状态机

```text
idle
-> chatting
-> waiting_confirm
-> executing
-> waiting_callback
-> updating_plan
-> executing
-> completed
```

含义如下：

- `chatting`：主 Agent 跟用户澄清需求
- `waiting_confirm`：主 Agent 已生成 plan，等待用户确认
- `executing`：worker 正在执行具体任务
- `waiting_callback`：worker 结果已产出，等待回投主 run
- `updating_plan`：主 Agent 收到 worker 结果，更新计划
- `completed`：整轮任务结束

---

## 8. worker 的回调机制

### 8.1 正确做法

worker 完成任务后，应当把结果转成一次新的 input，投递到主 run 对应的 `run_id`。

```text
worker 结束
-> 保存结果
-> 标记 subtask completed
-> 回调 POST /agent-runs/{run_id}/input
-> 主 Agent 继续执行
```

### 8.2 为什么不是“继续当前 worker”

因为 worker 的职责已经结束。

回调不是让 worker 自己继续跑，而是让**主 run** 接手结果，进入下一轮判断。

这样可以避免：

- worker 套 worker
- 调度链路递归
- 子任务误入主控逻辑

---

## 9. `run_id` 的语义

`run_id` 不是日志字段，而是 **一次 Agent 执行实例的主键**。

### 9.1 三个关键字段

```text
AgentRun
- run_id
- parent_run_id
- root_run_id
- agent_id
- agent_kind: orchestrator | worker
- status
- context_snapshot
- plan_path
- toolset
```

### 9.2 语义关系

- `run_id`：当前这次执行实例的 ID
- `parent_run_id`：当前 run 的直接父 run，worker 会指向主 run
- `root_run_id`：这一轮协作的根 run，整条链路都能追溯到它

### 9.3 典型关系

```text
root orchestrator run
- run_id = R1
- parent_run_id = null
- root_run_id = R1

worker run
- run_id = W1
- parent_run_id = R1
- root_run_id = R1
```

所以：

- 主 Agent 自己的 `run_id` 不会失效，只会暂停等待
- worker 回调时，应该回到主 Agent 的 `run_id`
- `POST /agent-runs/{run_id}/input` 里的 `run_id`，就是当前要被唤醒的那个运行实例

---

## 10. 最小数据结构

```text
Plan
- plan_id
- workspace_id
- run_id
- file_path: PLAN.md
- status
- updated_at
```

说明：

- `PLAN.md` 仍然保留，作为用户可见的计划文件
- `Plan` 在当前阶段不单独落库，先作为内存中的结构化状态
- 每次计划变更都要同步写入 `PLAN.md`

```text
InputEvent
- event_id
- run_id
- source_type: user | worker | system
- payload
- created_at
```

```text
Subtask
- subtask_id
- root_run_id
- parent_run_id
- worker_run_id
- status
- result_ref
```

---

## 11. 存储规范

这里的实现先按 **内存优先** 处理，不要求当前阶段落地 MySQL。

### 11.1 只保留当前接口需要的实体

这份接口方案当前只需要以下实体：

- `AgentRun`
- `InputEvent`
- `Subtask`
- `Plan`（结构化状态 + 原始文档内容）

不在这份文档里展开额外的用户表、权限表、审计表等内容。

### 11.2 统一通过 Repository 访问

接口层和 Service 层都不要直接操作具体数据库实现，而是通过 Repository 访问数据。

推荐结构：

```text
api
-> service
-> repository
-> in-memory store
```

当前阶段只需要先定义这些最小仓储能力：

- `AgentRunRepository`
- `InputEventRepository`
- `SubtaskRepository`
- `PlanRepository`

### 11.3 内存实现方式

开发阶段可以直接使用内存对象保存数据，便于在不同电脑上直接启动。

建议内部结构类似：

```text
InMemoryStore
- agent_runs
- input_events
- subtasks
- plans
```

必要时再加最小索引：

```text
- input_by_idempotency_key
- subtask_by_parent_run_id
```

### 11.4 `PLAN.md` 的归属

`PLAN.md` 是 Workspace 里的可视化文件，后端也要保留对应的原始计划文档。

推荐同步关系是：

```text
Plan document + state
-> sync to workspace/PLAN.md
-> worker callback 后继续更新同一份计划
```

### 11.5 这份文档与数据库规范的关系

更完整的存储规范放在根目录的 [数据库规范设计.md](</E:/Github/AgentHub-weon/docs/数据库规范设计.md>)。

这份 `AgentRun` 文档只引用其中最需要的部分，不再单独展开一整套存储架构。

当前阶段的实际落点是：

- `AgentRun`、`InputEvent`、`Subtask` 走内存仓储
- `Plan` 走内存仓储，但同时保留原始计划文档内容
- `PLAN.md` 始终保留并同步更新

---

## 12. 实现要点

- `POST /agent-runs/{run_id}/input` 只依赖 `run_id` 查询现有运行实例。
- worker 的结果必须先落内存仓储，再尝试回调主 run。
- 回调失败时，结果应保留在内存状态中，方便重试。
- 主 Agent 和 worker 共享同一个输入入口，但走不同的工具集和循环策略。
- `delegate_tool` 只负责创建异步 subtask，不负责等待执行完成。
- `PLAN.md` 始终保留，所有计划变更必须同步写入它。

---

## 13. 一句话总结

`POST /agent-runs/{run_id}/input` 是 AgentHub 的统一执行入口：用户输入进来时唤醒对应 Agent，worker 结果回来时再喂回主 Agent；存储层先按内存实现和 Repository 抽象落地，等流程稳定后再无缝切换到更正式的持久化实现。
