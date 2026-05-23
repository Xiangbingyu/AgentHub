# plan_tool 方案

## 一、目标

`plan_tool` 负责把模型生成的结构化计划，稳定落到系统内的 `Plan` 和可视化计划文件中，并为后续 `run_input` 的主循环提供明确的计划状态。

同时，`Plan` 不是像 skill 一样在每轮动态读取的外部附加资源，而是会作为 agent 的动态提示词上下文的一部分直接注入。`worker loop` 还会额外注入当前任务对应的局部计划视图，帮助模型聚焦当前子任务。

这份方案第一期不做用户确认，不做局部 patch，不做复杂计划版本管理。

## 二、定位

`plan_tool` 不是简单的 Markdown 写文件工具，而是一个 **结构化计划快照覆盖工具**。

它的职责是：

- 接收模型提交的完整 Plan 快照
- 全量覆盖当前 run 的计划内容
- 同步生成可视化计划文件
- 更新系统内的 Plan 状态
- 返回本轮计划处理结果

## 三、设计原则

- 每次提交一份新的完整 Plan
- 底层使用全量覆盖，不做局部 patch
- 计划结构由 tool 参数 schema 决定，不靠自然语言解析
- `Plan` 直接进入动态提示词上下文，不作为每轮外部动态读取的 skill
- `worker loop` 可注入当前任务的局部计划视图
- `PLAN.md` 不作为第一期文件名，改用业务语义更强的文件名
- `plan_tool` 负责计划写入，`loop` 负责控制流判定

## 四、文件路径规范

计划文件建议写入当前 workspace 下：

```text
<workspace>/.AgentHub/plans/{run_id}.execution-plan.md
```

推荐原因：

- 能按 `run_id` 隔离计划文件
- 能体现这是执行计划而不是通用文档
- 后续扩展 review / proposal / report 时命名体系更统一

## 五、提示词注入方式

### 5.1 `Plan` 的注入方式

`Plan` 应在运行时直接进入 agent 的动态提示词上下文，和 system / environment / instruction prompt 一起拼装。

它不是像 skill 一样按需动态读取的外部能力清单，而是当前 run 的实时状态快照。

建议注入内容包括：

- 当前 plan title / goal / summary
- 当前 steps
- 当前进度状态
- 当前 blocker / checkpoint
- 当前 run 关联的 workspace / run_id

### 5.2 `worker loop` 的局部计划视图

`worker loop` 不需要完整展示整个全局 plan，而应注入和当前任务直接相关的局部视图，例如：

- 当前子任务标题
- 子任务目标
- 与当前子任务直接相关的步骤
- 当前允许的工具边界

这样 worker 的 prompt 会更聚焦，也更适合只写代码、不发配子任务的执行模式。

## 六、数据结构

### 5.1 Plan

```text
Plan
- plan_id
- run_id
- workspace_id
- file_path
- title
- goal
- status
- summary
- steps
- raw_document
- updated_at
```

### 5.2 PlanStep

```text
PlanStep
- step_id
- content
- status
- priority
- owner_agent_id
```

### 5.3 状态枚举

- `pending`
- `in_progress`
- `completed`
- `cancelled`

## 七、tool 输入输出

### 6.1 输入

`plan_tool` 接收的是一份完整的结构化计划快照：

```json
{
  "title": "实现 agent run input 主流程",
  "goal": "完成 orchestrator 和 worker 的统一输入链路骨架",
  "summary": "当前已完成基础 run create，正在补 run input 主循环和工具边界。",
  "steps": [
    {
      "step_id": "step-1",
      "content": "实现统一 InputEvent 模型",
      "status": "completed",
      "priority": "high",
      "owner_agent_id": null
    }
  ]
}
```

### 6.2 输出

建议返回：

```json
{
  "plan_id": "uuid",
  "status": "updated",
  "file_path": "<workspace>/.AgentHub/plans/{run_id}.execution-plan.md",
  "summary": "Plan updated and synced"
}
```

## 八、核心流程

```text
1. 读取当前 run 对应的旧 Plan
2. 校验新输入是否为完整结构化快照
3. 生成新的 Plan 实体
4. 全量覆盖旧 Plan
5. 渲染 Markdown 文档
6. 写入 workspace/.AgentHub/plans/{run_id}.execution-plan.md
7. 更新内存中的 Plan.raw_document / summary / status
8. 返回 tool result
```

## 九、状态推导

Plan 总体状态建议按步骤状态推导：

- 全部 `completed` -> `completed`
- 存在 `in_progress` -> `in_progress`
- 全部 `pending` -> `pending`
- 全部 `cancelled` -> `cancelled`
- 其他混合情况 -> `in_progress`

## 十、Markdown 渲染模板

```md
# {title}

## Goal
{goal}

## Summary
{summary}

## Steps
- [ ] pending step
- [~] in progress step
- [x] completed step
- [-] cancelled step

## Meta
- Run ID: {run_id}
- Updated At: {updated_at}
```

状态映射：

- `pending` -> `[ ]`
- `in_progress` -> `[~]`
- `completed` -> `[x]`
- `cancelled` -> `[-]`

## 十一、与 loop 的职责边界

- `loop` 负责决定本轮是否继续、等待还是结束
- `plan_tool` 负责把计划完整写入系统
- `plan_tool` 不做 confirm 分支
- `plan_tool` 第一版不返回 `waiting_confirm`

## 十二、与 opencode Todo 的对应关系

`plan_tool` 借鉴 `opencode todowrite` 的核心思想：

- 结构化输入
- 全量覆盖
- 状态显式化
- 计划对用户可见

但 `plan_tool` 比 Todo 更偏向多 Agent 编排，因此需要保留：

- `goal`
- `summary`
- `owner_agent_id`
- `run_id`

## 十三、后续可扩展能力

第一期不强制实现，但后面可以补：

- `save_plan_file()`
- `load_plan_file()`

这两个能力适合放到文件访问层或 repository 里，用于后续文件同步和历史回放。

## 十四、一句话总结

`plan_tool` 的第一版应当是一个基于完整结构化快照的全量覆盖写入工具：接收模型整理好的 Plan，更新系统内的 Plan 和 workspace 下的计划文件，并把计划状态稳定交回给主 loop。
