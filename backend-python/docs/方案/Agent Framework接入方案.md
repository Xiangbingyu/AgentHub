# Agent Framework 接入方案

## 一、目标

这份文档不再重复 AgentHub 总方案里的平台职责、会话结构和 Orchestrator 设计，只聚焦一个问题：

- **如何把 `Claude Code` 或 `Codex` 接成 AgentHub 里的编程型 Agent Framework**

下面统一以 `Claude Code` 为主例，`Codex` 作为同类框架看待。

## 二、核心结论

- 不建议直接改 `Claude Code` 源码来接入。
- 更合理的方式是通过官方提供的可编程能力做适配。
- 目前更现实的接入方式有两种：
  - `Headless CLI`
  - `Agent SDK`
- 短期更适合先用 `Headless CLI` 跑通。
- 长期更适合升级为 `Agent SDK` 方案。

- **模型配置按框架能力决定**

## 三、Claude Code 的两种接入方案

目前更现实的 Claude Code 接入方式可以分成两种：

- `Headless CLI` 方案
- `Agent SDK` 方案

这两种方案的共同点是：

- 都不是纯离线包
- 都通常需要认证
- 都不是简单下载后完全本地运行
- 本质上都仍依赖 Claude 侧能力

因此一般需要：

- `ANTHROPIC_API_KEY`
- 或 Claude 所支持的其他 provider 认证方式

## 四、方案一：Headless CLI 接入

### 1. 基本思路

这种方案的核心是：

- 在 AgentHub 后端机器上安装一份 `Claude Code`
- 当某个 Agent 被配置为使用 `Claude Code Framework` 时
- 后端通过命令行方式启动 `claude` 的 headless 执行
- 把任务 prompt、工作目录、工具权限等参数传给它
- 等待执行结果，再回传给 AgentHub

也就是说，接入方式大致可以理解为：

```text
前端
-> AgentHub 后端
-> ClaudeCodeAdapter
-> spawn("claude", ...)
-> Claude Code 在指定 sandbox 中执行
-> 输出结果返回后端
-> 后端更新任务状态和结果
```

### 2. 一个简化示意

命令行示例：

```bash
claude -p "帮我写一个python脚本，包含一个函数，中序遍历二叉树" --allowedTools Read,Edit,Write
```

后端适配器示例：

```ts
spawn("claude", [
  "-p",
  prompt,
  "--allowedTools",
  "Read,Edit,Bash,Write",
  "--output-format",
  "json"
], {
  cwd: sandboxPath,
  env: {
    ...process.env,
    ANTHROPIC_API_KEY: "...",
  }
})
```

这里真正被转换的不是“代码”，而是：

- AgentHub 内部的任务对象
- 当前工作目录
- 当前工具权限
- 当前系统提示和上下文信息

然后 Claude Code 自己在目标目录中完成编码循环。

### 3. 部署方式

通常情况下：

- 全局安装一份 `Claude Code` CLI 就够了

不同 Agent 不需要各装一份。

真正需要隔离的是：

- `cwd`
- `sandboxPath`
- 环境变量
- 会话配置
- 当前任务 prompt

也就是说：

- CLI 安装是共享的
- 任务上下文和执行目录是隔离的

### 4. 优点

- 接入简单
- 成本低
- 适合快速验证
- 适合比赛项目先跑通链路
- 适合先做 `ClaudeCodeAdapter` 的 MVP

### 5. 缺点

- 对进程管理依赖更强
- 结构化控制能力不如 SDK 灵活
- 会话续跑、流式事件、审批桥接通常会更麻烦
- 长期维护不如 SDK 方案优雅

### 6. 适用阶段

更适合：

- 第一阶段原型
- 快速打通赛题要求
- 快速验证 AgentHub 与 Claude Code 的接入关系

## 五、方案二：Agent SDK 接入

### 1. 基本思路

这种方案的核心是：

- 不再把 Claude Code 当作外部命令行进程调用
- 而是直接使用官方的 `Agent SDK`
- 把 Claude Code 背后的 agent loop、tools、context management 当作程序库接入

这时链路可以理解为：

```text
前端
-> AgentHub 后端
-> ClaudeCodeAdapter
-> Claude Agent SDK
-> Claude Code 风格 agent loop
-> 结果事件回传给后端
```

### 2. 本质理解

SDK 方案不是“自己实现 Claude Code”，而是：

- 使用官方提供的 Claude Code 同源执行框架
- 再在 AgentHub 外层套一层 Adapter

这个 Adapter 主要负责：

- 任务启动
- 会话续跑
- 事件流桥接
- 用户输入桥接
- 结果标准化
- 与 `Workspace / Sandbox` 对接

### 3. 优点

- 更适合平台化集成
- 结构化控制能力更强
- 更适合做流式事件和多轮会话
- 更适合桥接 `question tool`
- 更适合长期架构演进

### 4. 缺点

- 接入复杂度更高
- 前期需要更认真地设计 Adapter
- 需要更清楚地理解官方 SDK 提供的控制面

### 5. 适用阶段

更适合：

- 第二阶段正式集成
- 需要更强会话控制能力的时候
- 需要把 Claude Code 更深地嵌入 AgentHub 主流程的时候

## 六、两种方案的关系

这两种方案不是二选一对立关系，而更适合看作：

- **先用 CLI/headless 跑通**
- **后用 Agent SDK 升级集成**

也就是说：

- `Headless CLI` 更像进程级适配
- `Agent SDK` 更像库级适配

平台的长期目标应是：

- `ClaudeCodeAdapter` 对上层暴露统一接口
- 底层实现可以先是 CLI 版
- 后续再切换为 SDK 版

## 七、ClaudeCodeAdapter 的职责

无论用哪种方案，`ClaudeCodeAdapter` 都不应只是一个简单“转发器”，而应承担统一桥接职责。

至少包括：

- 接收 AgentHub 派发任务
- 将任务转换为 Claude Code 可执行输入
- 绑定当前 `Workspace / Sandbox`
- 注入允许的工具和配置
- 接收执行中的输出与错误
- 将结果标准化为统一任务结果
- 支持任务取消
- 为后续会话续跑预留接口

## 八、建议的统一接口

可以先抽象成这样：

```ts
interface AgentFrameworkAdapter {
  startTask(input: {
    taskPrompt: string;
    workspacePath: string;
    sandboxPath?: string;
    frameworkConfig?: Record<string, unknown>;
  }): Promise<{ taskId: string }>;

  getTaskStatus(taskId: string): Promise<{
    status: "running" | "completed" | "failed";
    output?: string;
  }>;

  cancelTask(taskId: string): Promise<void>;

  resumeTask?(taskId: string, input: {
    prompt: string;
  }): Promise<void>;
}
```

然后具体实现：

- `ClaudeCodeAdapter`
- `CodexAdapter`

这样上层只面对统一接口，不直接依赖某个具体框架。

## 九、对 AgentHub 的推荐落地顺序

### 第一阶段

- 抽象 `Agent Framework Adapter`
- 实现 `ClaudeCodeAdapter`
- 底层先采用 `Headless CLI`
- 先跑通：
  - 任务派发
  - sandbox 目录绑定
  - 结果回传
  - plan 更新

### 第二阶段

- 把 `ClaudeCodeAdapter` 升级为 `Agent SDK` 版
- 增强：
  - 流式事件
  - 会话续跑
  - 用户提问和输入桥接
  - 更细粒度控制

### 第三阶段

- 增加 `CodexAdapter`
- 做统一的多框架配置体系
- 按框架能力决定模型配置和功能开关

## 十、一句话总结

AgentHub 接入 `Claude Code` 更合理的方式，不是修改其源码，而是通过官方可编程能力来封装 `ClaudeCodeAdapter`；其中短期可先采用 `Headless CLI` 方案快速跑通，长期则更适合升级为 `Agent SDK` 方案，并在平台层统一抽象为 `Agent Framework Adapter`，从而为后续接入 `Codex` 等其他框架预留一致接口。
