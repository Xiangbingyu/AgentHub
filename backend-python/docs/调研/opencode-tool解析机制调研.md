# opencode Tool 解析机制调研

## 结论

`opencode` 的 tool 解析不是靠提示词里解析 `Action:` / `Observation:` 这种文本格式，而是：

- 模型或 provider 先产出原生 tool call 事件
- 运行时把这些事件统一转换成内部 `LLMEvent`
- `SessionProcessor` 消费这些事件并更新 session 状态
- 再根据 tool 名称找到具体工具定义，执行 `execute()`
- 最后把 tool result / tool error 回写到 assistant message parts 中

所以它本质上是：

- **tool-calling runtime**
- **事件驱动的 tool 处理链路**
- **不是文本版 ReAct 解析**

## 整体链路

可以把 `opencode` 的 tool 解析链路理解成：

```text
LLM/provider 输出
-> 转成统一 LLMEvent
-> SessionProcessor.handleEvent()
-> 识别 tool-call / tool-result / tool-error
-> 更新 session 中的 tool part
-> 执行具体 Tool.execute()
-> 将结果写回 session
-> runLoop 决定继续还是退出
```

## 一、主循环入口

主循环在 `session/prompt.ts` 的 `runLoop()` 中。

它的职责是：

- 反复读取当前 session 最新消息
- 判断是否已经满足退出条件
- 调模型
- 把模型输出交给 `processor`
- 根据结果决定继续下一轮还是结束

关键代码：

```ts
while (true) {
  yield* status.set(sessionID, { type: "busy" })
  yield* slog.info("loop", { step })

  let msgs = yield* MessageV2.filterCompactedEffect(sessionID)

  const { user: lastUser, assistant: lastAssistant, finished: lastFinished, tasks } = MessageV2.latest(msgs)

  const lastAssistantMsg = msgs.findLast(
    (msg) => msg.info.role === "assistant" && msg.info.id === lastAssistant?.id,
  )
  const hasToolCalls =
    lastAssistantMsg?.parts.some((part) => part.type === "tool" && !part.metadata?.providerExecuted) ?? false

  if (
    lastAssistant?.finish &&
    !["tool-calls"].includes(lastAssistant.finish) &&
    !hasToolCalls &&
    lastUser.id < lastAssistant.id
  ) {
    yield* slog.info("exiting loop")
    break
  }

  ...

  const handle = yield* processor
```

这里最关键的是：

- `runLoop()` 自己决定何时退出
- 退出条件不是模型输出 `"stop"`
- 而是 runtime 判断：
  - assistant 已完成
  - 没有未处理 tool call
  - 当前回复已经覆盖最新用户输入

## 二、provider 输出如何转成统一事件

`opencode` 不直接在主循环里解析每个 provider 的原始响应，而是先统一事件格式。

关键代码在 `session/llm/ai-sdk.ts`。

例如，tool 输入开始、tool call、tool result、tool error 会被转换成统一 `LLMEvent`：

```ts
case "tool-input-start":
  return Effect.sync(() => {
    state.toolNames[event.id] = event.toolName
    return [
      LLMEvent.toolInputStart({
        id: event.id,
        name: event.toolName,
        providerMetadata: providerMetadata(event.providerMetadata),
      }),
    ]
  })

case "tool-call":
  return Effect.sync(() => {
    state.toolNames[event.toolCallId] = event.toolName
    return [
      LLMEvent.toolCall({
        id: event.toolCallId,
        name: event.toolName,
        input: event.input,
        providerExecuted: "providerExecuted" in event ? event.providerExecuted : undefined,
        providerMetadata: providerMetadata(event.providerMetadata),
      }),
    ]
  })

case "tool-result":
  return Effect.sync(() => {
    const name = state.toolNames[event.toolCallId] ?? "unknown"
    delete state.toolNames[event.toolCallId]
    return [
      LLMEvent.toolResult({
        id: event.toolCallId,
        name,
        result: ToolResultValue.make(event.output),
        providerExecuted: "providerExecuted" in event ? event.providerExecuted : undefined,
        providerMetadata: providerMetadata(event.providerMetadata),
      }),
    ]
  })

case "tool-error":
  return Effect.sync(() => {
    const name = state.toolNames[event.toolCallId] ?? ("toolName" in event ? event.toolName : "unknown")
    delete state.toolNames[event.toolCallId]
    return [
      LLMEvent.toolError({
        id: event.toolCallId,
        name,
        message: errorMessage(event.error),
        error: event.error,
        providerMetadata: providerMetadata(event.providerMetadata),
      }),
    ]
  })
```

这说明：

- tool 解析的第一步是**事件统一化**
- 后面的 processor 不需要关心 provider 原始格式

## 三、Tool 事件的核心处理器

最关键的代码在 `session/processor.ts` 的 `handleEvent()`。

它会按事件类型处理：

- `tool-input-start`
- `tool-input-end`
- `tool-call`
- `tool-result`
- `tool-error`

### 1. 识别 tool-call

当收到 `tool-call` 事件时，processor 会：

- 确保已有对应 tool call part
- 记录 tool 名称和 input
- 把 tool state 更新为 `running`
- 必要时触发防止 doom loop 的权限检查

关键代码：

```ts
case "tool-call": {
  if (ctx.assistantMessage.summary) {
    throw new Error(`Tool call not allowed while generating summary: ${value.name}`)
  }
  const toolCall = yield* ensureToolCall(value)
  const input = toolInput(value.input)

  yield* updateToolCall(value.id, (match) => ({
    ...match,
    tool: value.name,
    state:
      match.state.status === "running"
        ? { ...match.state, input }
        : {
            status: "running",
            input,
            time: { start: Date.now() },
          },
    metadata: match.metadata?.providerExecuted
      ? { ...value.providerMetadata, providerExecuted: true }
      : value.providerMetadata,
  }))

  ...
  return
}
```

这里说明：

- `tool-call` 不是文本解析
- 而是直接把 tool 名称和参数转成 session 内部状态

### 2. 处理 tool-result

当 tool 执行成功返回后，processor 会：

- 读取对应 tool call
- 归一化输出和附件
- 发布成功事件
- 调 `completeToolCall()` 把结果写回 session

关键代码：

```ts
case "tool-result": {
  const toolCall = yield* readToolCall(value.id)
  const rawOutput = toolResultOutput(value)
  ...
  const output = {
    ...rawOutput,
    output:
      omitted === 0
        ? rawOutput.output
        : `${rawOutput.output}\n\n[${omitted} image${omitted === 1 ? "" : "s"} omitted: could not be resized below the image size limit.]`,
    attachments: attachments.length ? attachments : undefined,
  }

  yield* completeToolCall(value.id, output)
  return
}
```

### 3. 处理 tool-error

当工具失败时，processor 会：

- 发布失败事件
- 把对应 tool call 标成 failed

关键代码：

```ts
case "tool-error": {
  const toolCall = yield* readToolCall(value.id)
  ...
  yield* failToolCall(value.id, value.error ?? new Error(value.message))
  return
}
```

## 四、Tool 基座是怎么定义的

`opencode` 的工具不是随便写个函数，而是有统一基座，核心在 `tool/tool.ts`。

### 1. 工具定义结构

每个工具都有：

- `id`
- `description`
- `parameters`
- `execute()`

关键类型：

```ts
export interface Def<
  Parameters extends Schema.Decoder<unknown> = Schema.Decoder<unknown>,
  M extends Metadata = Metadata,
> {
  id: string
  description: string
  parameters: Parameters
  jsonSchema?: JSONSchema7
  execute(args: Schema.Schema.Type<Parameters>, ctx: Context): Effect.Effect<ExecuteResult<M>>
  formatValidationError?(error: unknown): string
}
```

### 2. 参数校验

工具参数不是手写解析，而是通过 schema 自动校验。

关键代码：

```ts
const decode = Schema.decodeUnknownEffect(toolInfo.parameters)
...
const decoded = yield* decode(args).pipe(
  Effect.mapError(
    (error) =>
      new InvalidArgumentsError({
        tool: id,
        detail: toolInfo.formatValidationError ? toolInfo.formatValidationError(error) : String(error),
      }),
  ),
)
const result = yield* execute(decoded as Schema.Schema.Type<Parameters>, ctx)
```

这说明：

- tool 解析里不仅有“识别调用”
- 还有“参数校验失败时返回给模型重写”

这也是 `opencode` tool 机制比较成熟的一点。

## 五、以 `todowrite` 为例看具体工具

`todowrite` 是一个很典型的例子，因为它正好体现了：

- tool 参数 schema
- 工具执行
- session 状态更新

### 1. 参数 schema

```ts
const TodoItem = Schema.Struct({
  content: Schema.String.annotate({ description: "Brief description of the task" }),
  status: Schema.String.annotate({
    description: "Current status of the task: pending, in_progress, completed, cancelled",
  }),
  priority: Schema.String.annotate({ description: "Priority level of the task: high, medium, low" }),
})

export const Parameters = Schema.Struct({
  todos: Schema.mutable(Schema.Array(TodoItem)).annotate({ description: "The updated todo list" }),
})
```

### 2. 工具定义与执行

```ts
export const TodoWriteTool = Tool.define<typeof Parameters, Metadata, Todo.Service>(
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

这里可以清楚看出：

- 模型不是输出自然语言“请帮我更新 todo”
- 而是直接调用 `todowrite`
- 并把 `todos` 结构化数据作为参数传进去
- 工具执行后再把结果作为 tool result 返回

## 六、Tool 是怎么创建的

`opencode` 里的工具不是直接塞一个普通函数给模型，而是先通过 `Tool.define()` 定义成统一的工具信息对象。

以 `todowrite` 为例：

```ts
export const TodoWriteTool = Tool.define<typeof Parameters, Metadata, Todo.Service>(
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

这里的创建过程本质上是：

- 先声明 tool id
- 再声明参数 schema
- 再声明 description
- 最后给出 `execute()`

也就是说，一个工具在进入系统前就已经具备了：

- 结构化参数
- LLM 可见说明
- 统一执行入口

## 七、Tool 是怎么注册的

工具不会在各处零散使用，而是统一收敛到 `tool/registry.ts`。

### 1. 先实例化内置工具

注册表在初始化时，会把所有内置工具都取出来：

```ts
const invalid = yield* InvalidTool
const task = yield* TaskTool
const taskStatus = yield* TaskStatusTool
const read = yield* ReadTool
const question = yield* QuestionTool
const todo = yield* TodoWriteTool
const lsptool = yield* LspTool
const plan = yield* PlanExitTool
const webfetch = yield* WebFetchTool
const websearch = yield* WebSearchTool
const repoClone = yield* RepoCloneTool
const repoOverview = yield* RepoOverviewTool
const shell = yield* ShellTool
const globtool = yield* GlobTool
const writetool = yield* WriteTool
const edit = yield* EditTool
const greptool = yield* GrepTool
const patchtool = yield* ApplyPatchTool
const skilltool = yield* SkillTool
```

然后通过 `Tool.init()` 完成真正初始化：

```ts
const tool = yield* Effect.all({
  invalid: Tool.init(invalid),
  shell: Tool.init(shell),
  read: Tool.init(read),
  glob: Tool.init(globtool),
  grep: Tool.init(greptool),
  edit: Tool.init(edit),
  write: Tool.init(writetool),
  task: Tool.init(task),
  task_status: Tool.init(taskStatus),
  fetch: Tool.init(webfetch),
  todo: Tool.init(todo),
  search: Tool.init(websearch),
  repo_clone: Tool.init(repoClone),
  repo_overview: Tool.init(repoOverview),
  skill: Tool.init(skilltool),
  patch: Tool.init(patchtool),
  question: Tool.init(question),
  lsp: Tool.init(lsptool),
  plan: Tool.init(plan),
})
```

这里说明：

- `Tool.define()` 负责定义
- `Tool.init()` 负责初始化成真正可注册的工具

### 2. 再组合成内置工具列表

初始化后的工具会根据 runtime flags 决定是否启用：

```ts
return {
  custom,
  builtin: [
    tool.invalid,
    ...(questionEnabled ? [tool.question] : []),
    tool.shell,
    tool.read,
    tool.glob,
    tool.grep,
    tool.edit,
    tool.write,
    tool.task,
    ...(flags.experimentalBackgroundSubagents ? [tool.task_status] : []),
    tool.fetch,
    tool.todo,
    tool.search,
    ...(flags.experimentalScout ? [tool.repo_clone, tool.repo_overview] : []),
    tool.skill,
    tool.patch,
    ...(flags.experimentalLspTool ? [tool.lsp] : []),
    ...(flags.experimentalPlanMode && flags.client === "cli" ? [tool.plan] : []),
  ],
  task: tool.task,
  read: tool.read,
}
```

也就是说：

- 不是所有定义出来的工具都会无条件暴露
- 最终暴露集合还会受：
  - client 类型
  - 实验开关
  - 模式开关
  的影响

### 3. 自定义 tool / plugin tool 也会进注册表

`registry.ts` 还会自动扫描：

- `{tool,tools}/*.{js,ts}`
- plugin 暴露的 `tool`

然后统一转成 `Tool.Def`。

关键代码：

```ts
const matches = dirs.flatMap((dir) =>
  Glob.scanSync("{tool,tools}/*.{js,ts}", { cwd: dir, absolute: true, dot: true, symlink: true }),
)

for (const match of matches) {
  const namespace = path.basename(match, path.extname(match))
  const mod = yield* Effect.promise(() => import(pathToFileURL(match).href))
  for (const [id, def] of Object.entries(mod)) {
    if (!isPluginTool(def)) continue
    custom.push(fromPlugin(id === "default" ? namespace : `${namespace}_${id}`, def))
  }
}

const plugins = yield* plugin.list()
for (const p of plugins) {
  for (const [id, def] of Object.entries(p.tool ?? {})) {
    custom.push(fromPlugin(id, def))
  }
}
```

这说明：

- `opencode` 不只有内置工具
- 自定义工具和插件工具也走统一注册表

## 八、Tool 是怎么传给模型的

注册好的工具不会直接原样塞给模型，还会经过一层 `session/tools.ts` 包装成 AI SDK 可识别的工具对象。

### 1. 从 ToolRegistry 取出可用工具

```ts
for (const item of yield* registry.tools({
  modelID: ModelID.make(input.model.api.id),
  providerID: input.model.providerID,
  agent: input.agent,
})) {
  ...
}
```

### 2. 转成 AI SDK 的 `tool(...)`

```ts
tools[item.id] = tool({
  description: item.description,
  inputSchema: jsonSchema(schema),
  execute(args, options) {
    return run.promise(
      Effect.gen(function* () {
        const ctx = context(args, options)
        yield* plugin.trigger(
          "tool.execute.before",
          { tool: item.id, sessionID: ctx.sessionID, callID: ctx.callID },
          { args },
        )
        const result = yield* item.execute(args, ctx)
        ...
        yield* plugin.trigger(
          "tool.execute.after",
          { tool: item.id, sessionID: ctx.sessionID, callID: ctx.callID, args },
          output,
        )
        return output
      }),
    )
  },
})
```

这里很关键，说明：

- 注册表中的 `Tool.Def`
- 会被包装成 provider/AI SDK 能识别的执行对象
- `execute()` 最终仍然回到 `item.execute(args, ctx)` 这条统一接口

### 3. 再经过请求准备阶段筛选

在 `session/llm/request.ts` 中，真正送给模型前还会按权限和用户配置再过滤一遍：

```ts
function resolveTools(input: Pick<PrepareInput, "tools" | "agent" | "permission" | "user">) {
  const disabled = Permission.disabled(
    Object.keys(input.tools),
    Permission.merge(input.agent.permission, input.permission ?? []),
  )
  return Record.filter(input.tools, (_, k) => input.user.tools?.[k] !== false && !disabled.has(k))
}
```

也就是说：

- 工具是否最终出现在模型可见工具列表里
- 不只由注册表决定
- 还要看：
  - agent 权限
  - session 权限
  - user 是否显式禁用了某些 tool

## 九、完整闭环

把前面的“创建、注册、解析、执行”连起来，就是：

```text
Tool.define()
-> Tool.init()
-> ToolRegistry 收集 builtin/custom/plugin tools
-> SessionTools.resolve() 包装成 AI SDK tool
-> LLMRequestPrep.resolveTools() 按权限过滤
-> 模型发起 tool-call
-> ai-sdk.ts 转成统一 LLMEvent
-> SessionProcessor 处理 tool-call / tool-result / tool-error
-> item.execute(args, ctx)
-> 回写 session
-> runLoop 决定继续还是退出
```

## 十、processor 的返回值和 loop 的关系

`SessionProcessor.process()` 在处理完一轮流后，不直接输出自然语言控制词，而是返回内部控制结果：

```ts
if (ctx.needsCompaction) return "compact"
if (ctx.blocked || ctx.assistantMessage.error) return "stop"
return "continue"
```

也就是说：

- tool 是否成功
- 是否阻塞
- 是否报错
- 是否需要压缩

这些都会影响 loop 的后续走向。

但真正决定整个主循环是否退出的，还是外层 `runLoop()` 的退出条件。

## 十一、对 AgentHub 的启发

如果要借鉴 `opencode` 的 tool 解析机制，最值得学的是：

- **先统一 provider 事件**
- **再用 processor 做 tool-call / tool-result / tool-error 的单点处理**
- **把 Tool 的创建、注册和执行分成独立层次**
- **工具定义统一走 schema + execute**
- **参数校验失败时让模型重写，而不是静默吞掉**
- **主 loop 只负责控制流，不负责散写工具解析逻辑**

最不建议直接照搬的是：

- 整套 `Effect` 风格运行时
- 它完整的 session 事件系统
- CLI/TUI 强绑定部分

## 一句话总结

`opencode` 的 tool 机制不是简单“模型调函数”，而是一条完整的 runtime 链路：工具先通过 `Tool.define()` 创建，再经 `ToolRegistry` 注册、`SessionTools.resolve()` 包装、`LLMRequestPrep` 过滤后暴露给模型；provider 输出的 tool 事件再被统一转换成 `LLMEvent`，由 `SessionProcessor` 处理并调用具体工具的 `execute()`，最后把结果回写到 session。
