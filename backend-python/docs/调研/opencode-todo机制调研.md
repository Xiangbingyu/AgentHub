# opencode Todo 机制调研

## 结论

`opencode` 里确实有一套真正的 Todo 机制，核心是 `todowrite`。

它的定位不是复杂的多 Agent `Plan`，而是当前会话里的轻量任务表，用来：

- 规划接下来几步
- 标记当前执行状态
- 在执行过程中持续更新任务表

它最关键的设计是：

- **每次提交一份新的完整 Todo 列表**
- **底层是全量覆盖，不是局部 patch**

## 机制概览

`todowrite` 的数据结构很简单，每个任务只有：

- `content`
- `status`
- `priority`

状态主要包括：

- `pending`
- `in_progress`
- `completed`
- `cancelled`

所以它更像“会话级任务清单”，而不是带依赖、带版本、带 assignee 的结构化执行计划。

## 格式化计划是怎么生成的

是的，`opencode` 的 Todo 机制本质上就是：

- 定义一个 `todowrite` tool
- 给这个 tool 规定固定参数结构
- 模型在需要规划时，直接把“当前最新 Todo 列表”填进参数里
- tool 再把这份列表整体写入当前 session

也就是说，它不是让模型自由输出一段 Markdown 计划表，再由系统去解析；而是：

- **模型通过工具调用**
- **按参数 schema 提交结构化 Todo 数据**

## Tool 参数结构

`todowrite` 的参数非常简单，只有一个字段：

- `todos`

而 `todos` 是一个数组，数组中的每一项都包含：

- `content`
- `status`
- `priority`

可以理解成：

```json
{
  "todos": [
    {
      "content": "Research existing metrics code",
      "status": "in_progress",
      "priority": "high"
    },
    {
      "content": "Implement export feature",
      "status": "pending",
      "priority": "medium"
    }
  ]
}
```

所以它生成“格式化计划”的方式就是：

- 模型组织出一份结构化数组
- 通过 `todowrite` 提交
- 系统再把这个数组显示成用户看到的任务表

## 相关代码

### 1. Tool 定义

这里做了三件事：

- 定义 `TodoItem` 的字段结构
- 定义 `Parameters = { todos: TodoItem[] }`
- 在 `execute()` 里调用 `todo.update(...)` 写入 session

核心形态就是：

```ts
const TodoItem = Schema.Struct({
  content: Schema.String,
  status: Schema.String,
  priority: Schema.String,
})

export const Parameters = Schema.Struct({
  todos: Schema.mutable(Schema.Array(TodoItem)),
})
```

然后在执行时：

```ts
export const TodoWriteTool = Tool.define(
  "todowrite",
  Effect.gen(function* () {
    const todo = yield* Todo.Service

    return {
      description: DESCRIPTION_WRITE,
      parameters: Parameters,
      execute: (params, ctx) =>
        Effect.gen(function* () {
          yield* ctx.ask({
            permission: "todowrite",
            patterns: ["*"],
            always: ["*"],
            metadata: {},
          })

yield* todo.update({
  sessionID: ctx.sessionID,
  todos: params.todos,
})

          return {
            title: `${params.todos.filter((x) => x.status !== "completed").length} todos`,
            output: JSON.stringify(params.todos, null, 2),
            metadata: {
              todos: params.todos,
            },
          }
        }),
    }
  }),
)
```

这说明：

- Todo 计划表不是模型直接写文件
- 而是通过 tool 参数提交

### 2. Session 持久化

这里的实现方式是：

- 先删掉当前 session 的旧 Todo
- 再按新数组顺序重新插入
- 最后发布 `todo.updated` 事件

关键逻辑如下：

```ts
const update = Effect.fn("Todo.update")(function* (input) {
  yield* Effect.sync(() =>
    Database.transaction((db) => {
      db.delete(TodoTable).where(eq(TodoTable.session_id, input.sessionID)).run()
      if (input.todos.length === 0) return
      db.insert(TodoTable)
        .values(
          input.todos.map((todo, position) => ({
            session_id: input.sessionID,
            content: todo.content,
            status: todo.status,
            priority: todo.priority,
            position,
          })),
        )
        .run()
    }),
  )
  yield* bus.publish(Event.Updated, input)
})
```

这也是为什么它属于：

- **全量覆盖**

而不是：

- **局部 patch**

### 3. Tool 说明文案

这份说明会作为 tool description 暴露给模型，用来告诉模型：

- 什么时候该用 Todo
- 什么时候不该用
- 状态有哪些
- 更新规则是什么

关键原文如下：

```text
Create and maintain a structured task list for the current coding session. Tracks progress, organizes multi-step work, and surfaces status to the user.

## When to use
Use proactively when:
- The task requires 3+ distinct steps or actions
- The work is non-trivial and benefits from planning
- New instructions arrive - capture them as todos
- You start a task - mark it `in_progress`
- You finish a task - mark it `completed`

## States
- `pending` - not started
- `in_progress` - actively working (exactly ONE at a time)
- `completed` - finished successfully
- `cancelled` - no longer needed

## Rules
- Update status in real time; don't batch completions
- Keep exactly one `in_progress` while work remains
- Items should be specific and actionable
```

## 模型是怎么把计划表填进去的

在 `opencode` 里，模型不会输出类似：

- “以下是我的计划”
- “1. 先做这个 2. 再做那个”

然后让系统从自然语言里抽取计划。

它的做法是：

1. 系统提示词告诉模型应该频繁使用 `TodoWrite`
2. tool description 告诉模型参数结构和使用规则
3. 模型在合适时机直接发起 `todowrite` tool call
4. 参数里直接带上一整个 `todos` 数组

也就是说，“格式化”本身来自：

- tool schema
- 不是来自 Markdown 解析

## 状态怎么修改

在 `opencode` 里，Todo 状态不是按单条任务局部修改的。

它的做法是：

- 模型重新组织一份最新的 Todo 列表
- 把某些项改成 `in_progress` 或 `completed`
- 再调用一次 `todowrite`
- 系统用这份新列表覆盖旧列表

也就是说，“给某一步打钩”在语义上成立，但在实现上其实是：

- **整表重写**

## 如果只想改 Plan 的一部分怎么办

也是一样，还是整表重写。

比如：

- 想修改某一步状态
- 想新增一步
- 想删掉一步
- 想调整顺序

这些在 `opencode` 里都不会走局部 patch，而是：

- 重新提交一份新的完整 Todo 数组

所以它属于：

- **快照式更新**

而不是：

- **差量式更新**

## 提示词规范

`opencode` 的官方提示词对 `TodoWrite` 有比较明确的使用要求，大意是：

- 多步骤任务要先写 Todo
- 复杂任务要用 Todo 拆解
- 开始做某项前先标 `in_progress`
- 做完后立刻标 `completed`
- 不要攒一批任务最后再统一更新
- 要高频使用 Todo，让用户看到当前进度

这说明在 `opencode` 里，Todo 不是可有可无的小功能，而是执行过程中的显式规划工具。

这些提示词主要来自两部分。

前者更像：

- 主系统提示词中关于任务规划和 Todo 的要求

后者更像：

- `todowrite` 这个工具本身的使用说明

主系统提示里的关键部分如下：

```text
# Task Management
You have access to the TodoWrite tools to help you manage and plan tasks. Use these tools VERY frequently to ensure that you are tracking your tasks and giving the user visibility into your progress.
These tools are also EXTREMELY helpful for planning tasks, and for breaking down larger complex tasks into smaller steps. If you do not use this tool when planning, you may forget to do important tasks - and that is unacceptable.

It is critical that you mark todos as completed as soon as you are done with a task. Do not batch up multiple tasks before marking them as completed.
```

### 原文摘录

以下保留 `opencode` 中与 `TodoWrite` 相关的英文原文，便于后续直接对照实现：

```text
# Task Management
You have access to the TodoWrite tools to help you manage and plan tasks. Use these tools VERY frequently to ensure that you are tracking your tasks and giving the user visibility into your progress.
These tools are also EXTREMELY helpful for planning tasks, and for breaking down larger complex tasks into smaller steps. If you do not use this tool when planning, you may forget to do important tasks - and that is unacceptable.

It is critical that you mark todos as completed as soon as you are done with a task. Do not batch up multiple tasks before marking them as completed.
```

```text
IMPORTANT: Always use the TodoWrite tool to plan and track tasks throughout the conversation.
```

```text
Create and maintain a structured task list for the current coding session. Tracks progress, organizes multi-step work, and surfaces status to the user.

## When to use
Use proactively when:
- The task requires 3+ distinct steps or actions (not just 3 tool calls for a single conceptual step)
- The work is non-trivial and benefits from planning
- The user provides multiple tasks (numbered or comma-separated) or explicitly asks for a todo list
- New instructions arrive - capture them as todos
- You start a task - mark it `in_progress` (only one at a time) before working
- You finish a task - mark it `completed` and add any follow-ups discovered during the work

## When NOT to use
Skip when:
- The work is a single, straightforward task (or <3 trivial steps)
- The request is purely informational or conversational
- Tracking adds no organizational value

## States
- `pending` - not started
- `in_progress` - actively working (exactly ONE at a time)
- `completed` - finished successfully
- `cancelled` - no longer needed

## Rules
- Update status in real time; don't batch completions
- Mark `completed` only after the required work is actually done, including any required verification. Never based on intent.
- Keep exactly one `in_progress` while work remains
- If blocked or partial, keep it `in_progress` and add a follow-up todo describing the blocker
- Preserve user-provided commands verbatim (flags, args, order)
- Items should be specific and actionable; break large work into smaller steps
```

## 设计特点

这个机制有几个明显特点：

- Todo 是对用户可见的
- Todo 会跟随会话保存
- 更新后会同步到界面
- 更适合单会话任务跟踪
- 不适合直接承担复杂 Orchestrator 计划
- 结构化格式来自 tool 参数 schema
- 规划表的生成依赖模型主动调用 `todowrite`
- 系统不需要从自然语言计划中再做二次解析

另外，`todowrite` 默认更偏向主会话使用，不是让每个子 Agent 各自维护一套局部计划。

## 对 AgentHub 的启发

如果 AgentHub 想借鉴这套设计，可以借鉴的是：

- 用一个轻量 `todo` 工具把当前执行过程显式写出来
- 让任务状态及时更新，对用户可见
- 对复杂任务先列任务表，再执行

但不建议直接把它当成 Orchestrator 的 `plan`。

更合理的分层是：

- `todo` 负责会话级任务跟踪
- `plan` 负责多 Agent 编排、依赖关系和版本演进

## 一句话总结

`opencode` 的 `todowrite` 本质上是一个会话级轻量任务表工具：系统先定义 `todos: TodoItem[]` 的工具参数 schema，再由模型通过 tool call 把当前完整 Todo 列表作为结构化参数提交；底层用整表覆盖来更新 session 中的任务表。它适合做执行过程可视化，不适合直接充当复杂多 Agent 的结构化 Plan。
