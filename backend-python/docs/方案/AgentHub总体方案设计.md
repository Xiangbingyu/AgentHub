# AgentHub 总体方案设计

## 一、方案定位

AgentHub 不是一个普通的 AI 聊天产品，而是一套面向真实工程协作的多 Agent 协同系统。

它要解决的核心问题是：

- 用户与多个专业 Agent 协作时，如何同时保留自然对话体验和工程执行秩序
- 多 Agent 如何围绕同一个项目进行拆解、调度、执行、审阅和结果沉淀
- 长对话、长任务和多轮协作中，如何控制上下文长度并保留关键记忆
- 聊天、代码落地、Proposal、Sandbox、Git 和版本记录之间，如何形成闭环

这套系统的总体思路可以概括为一句话：

- **聊天负责沟通，Orchestrator 负责编排，Workspace 负责落地，Memory 负责长期连续性。**

## 二、设计目标

### 1. 协作目标

- 支持用户与多个默认 Agent、多个自定义 Agent 的协作
- 支持单聊、群聊、群内单聊三种会话形态
- 支持主 Agent 统一拆解、调度、汇总
- 支持用户直接和某个专业 Agent 对话

### 2. 工程目标

- 让聊天与代码真源分离
- 让 Agent 在隔离 Sandbox 中执行
- 让所有代码改动先沉淀为 Proposal，再进入确认流程
- 让项目真源、版本记录和 Git 语义保持清晰对应

### 3. 系统目标

- 支持动态 Plan 驱动的持续编排
- 支持长会话压缩和跨 session 长期记忆
- 支持默认 Agent + Skill 的可扩展体系
- 支持从 MVP 平滑演进到更复杂的多 Agent 协同系统

## 三、核心对象

### 1. 用户

用户是目标提出者、优先级决定者和最终审批者。

用户可以：

- 直接和某个 Agent 单聊
- 在群聊中与多个 Agent 协作
- 直接 `@Orchestrator` 请求拆解、调度、汇总
- 确认 Proposal、继续下一轮任务或改变目标

### 2. Agent

Agent 是系统中的专业角色执行者。每个 Agent 有自己的角色定位、提示词、权限和 Skill 组合。

系统默认提供几个预配置 Agent：

- `Frontend Engineer`：前端实现、页面结构、组件、交互、样式
- `Backend Engineer`：接口、服务、数据结构、持久化、任务流
- `Product Manager`：需求梳理、功能拆解、验收条件、优先级建议
- `System Architect`：系统设计、模块边界、技术选型、架构风险

后续还可以扩展：

- `Test Engineer`
- `Review Engineer`
- `DevOps Engineer`
- `Document Agent`

### 3. Orchestrator

`Orchestrator` 是主控 Agent，负责：

- 理解用户目标
- 生成和维护当前 Plan
- 拆解任务
- 判断依赖关系和并行关系
- 选择合适的子 Agent
- 跟踪任务状态
- 在任务完成、失败、阻塞或用户插入指令时重新检查
- 必要时触发 redispatch 或 replan

`Orchestrator` 更像项目经理和调度中心，而不是默认亲自承担大量编码工作。

### 4. Workspace

Workspace 是系统的顶层协作空间，是项目、Proposal、执行环境和版本沉淀的归属边界。

它不是天然唯一绑定在用户账号上的默认空间，而是由用户手动创建和选择。

## 四、总体架构

总体上，AgentHub 可以分成四个核心层次：

### 1. 会话协作层

负责承载用户与 Agent 的交互，包括：

- 单聊
- 群聊
- 群内单聊

这一层负责沟通、任务输入、状态展示和结果解释，但不直接作为代码真源。

### 2. 编排控制层

由 `Orchestrator` 主导，负责：

- 接收目标
- 生成 Plan
- 派发任务
- 回收结果
- 更新 Plan
- 判断是否继续、重试、重调度或重规划

这一层是多 Agent 协作的控制中心。

### 3. 工程落地层

由 `Workspace / Project Workspace / Proposal Pool / Sandbox / Version History` 构成，负责：

- 承载项目源码和配置
- 提供隔离执行环境
- 汇总 Proposal
- 沉淀版本记录

这一层负责让聊天中的协作真正落到工程资产上。

### 4. 记忆与上下文层

负责解决长对话和长期协作问题，包括：

- 当前 session 压缩
- `mem0`
- `memory.md`

这一层的目标是控制上下文长度，并保留跨轮、跨 session 的高价值信息。

## 五、会话模型

### 1. 群聊

群聊是主工作流，负责：

- 公开讨论
- 任务创建与调整
- 分工协作
- 结果确认
- 执行类指令发布

凡是会影响整体协作状态的动作，都应收口到群聊主线程。

### 2. 群内单聊

群内单聊是从群聊派生出来的辅助咨询通道。

特点是：

- Agent 可以读取所在群聊的上下文
- 用户可以针对某个 Agent 进行定向追问
- 新消息默认不自动进入群聊
- 只支持咨询，不支持直接执行和改任务

如果用户希望把有价值内容同步回群聊，应通过显式转发完成。

### 3. 普通单聊

普通单聊是用户和单个 Agent 的独立会话，不默认继承某个群聊的历史。

从产品语义上说：

- **单聊可以被视为一种小型群聊**

区别只是：

- 没有 `Orchestrator`
- 没有多个协作 Agent
- 只有一个具体 Agent 在处理用户请求

因此单聊仍然可以复用群聊的大部分基础设施，只是协作规模更小、控制关系更简单。

## 六、Workspace 设计

Workspace 方案的核心原则是：

- **聊天负责沟通，Workspace 负责落地**

### 1. 分层结构

系统中的工程落地结构分为六层：

- `Workspace`
- `Project Workspace`
- `Proposal Pool`
- `Agent Sandbox`
- `Execution Environment`
- `Version History`

### 2. 关键规则

- 聊天挂载 Workspace 后，才进入代码协作态
- 一个会话在任意时刻只应绑定一个 Workspace
- 切换 Workspace 等于切换协作语境，应清空当前执行态上下文
- Agent 默认只访问当前会话绑定且已授权的 Project Workspace
- Agent 不应直接写回项目真源，而应先在 Sandbox 中生成 Proposal

### 3. Proposal 流程

代码落地流程应为：

```text
Project Workspace
-> Agent Sandbox
-> Proposal Pool
-> Confirm
-> Version History
```

当 Git 接入后，这一流程可映射为：

```text
Main Branch
-> Proposal Branch
-> Merge
-> Push
-> Deploy
```

其中：

- `Confirm` 表示确认并合并进项目主线
- `Push` 表示同步到远端仓库
- `Deploy` 表示发布到运行环境

这三个动作应严格分离。

## 七、动态 Plan 编排设计

### 1. Plan 的定位

`Plan` 不是独立 Agent，而是 `Orchestrator` 内部维护的一份结构化状态。

它至少要承载：

- 当前目标
- 当前任务列表
- 任务状态
- 任务之间的先后关系或阶段关系
- 当前检查点
- 当前执行进度

### 2. 运行原则

AgentHub 采用 **动态 Plan 模式**，而不是一次性冻结计划后执行到底。

默认规则是：

- 每个任务完成后，触发一次 `Orchestrator` 检查
- 每个任务失败后，也触发一次 `Orchestrator` 检查
- 优先执行 `check`
- 如无须改计划，则执行 `redispatch`
- 只有当前计划不再适用时，才进入 `replan`

### 3. 三个关键动作

- `check`：重新检查当前计划状态
- `redispatch`：Plan 主体不变，只重新决定下一个任务派给谁
- `replan`：原计划不再适用时，保留有效部分并重建后续步骤

### 4. 默认行为

正常情况下，系统不应频繁重写整张 Plan，而应优先：

- 更新任务状态
- 选择已解锁的下一步
- 选择合适的 Agent
- 推进任务继续执行

### 5. 失败处理

任务失败后不应简单理解为“整轮重新开始”，而应由 `Orchestrator` 判断：

- 是直接重试当前任务
- 还是插入补救任务
- 还是进入局部 replan
- 还是重建当前检查点之后的计划

### 6. 并发处理

第一版更适合采用阶段式并发模型：

- 同一阶段内的任务可以并发分发给多个 Agent
- 等这一阶段的并发任务全部结束后
- 再进入下一阶段的同步任务

也就是：

- 简单串行任务可以直接执行
- 多 Agent 并发任务则按阶段推进

这样既能支持并发，又不必一开始就引入复杂依赖图。

### 7. 用户介入机制：`question tool`

为了让用户能够在开发过程中持续介入，而不是只在开始和结束时发言，`Orchestrator` 应具备专门的 `question tool`。

这套机制的定位不是普通聊天追问，而是结构化地向用户发问，用于：

- 澄清当前任务结果是否符合预期
- 让用户在多个后续方向之间做选择
- 在进入下一步 Plan 前确认优先级和约束
- 在失败、阻塞或阶段完成时请求用户决策

默认编排规则可以设计为：

- 每个关键任务完成后，先由 `Orchestrator` 做一次 `check`
- 如果当前阶段存在分支选择、目标确认或风险决策，则触发 `question tool`
- 用户回答后，再决定是 `redispatch` 还是 `replan`
- 若当前任务是低风险、无歧义的连续执行任务，则可跳过提问直接推进

这样设计的好处是：

- 用户可以随时介入每一步开发
- 系统不会在错误方向上长距离自动推进
- 动态 Plan 不再只是系统内部循环，而是带有人在环的持续协作流程

## 八、记忆与 Session 设计

这版 MVP 的记忆设计目标只有一个：

- **长群聊和长任务不能把全部历史一直塞进当前上下文**

### 1. 当前 session 的上下文策略

当前 session 仍然保存原始消息，但模型实际看到的上下文应为：

```text
head messages
-> summary
-> tail messages
```

也就是：

- 顶部稳定信息
- 中段压缩摘要
- 最新活跃消息

### 2. Compression

当消息过长时，只压缩中段，不切分复杂 session lineage。

压缩摘要至少应包含：

- 当前主题
- 已完成事项
- 未完成事项
- 当前任务状态
- 当前阻塞点
- 重要决策
- 重要文件、Proposal、分支信息

### 3. 长期记忆

长期记忆分两层：

- `mem0`：跨 session 的长期偏好、规则和稳定事实
- `memory.md`：项目运行中的关键记忆板

整体策略是：

```text
近处靠 compression
远处靠 mem0
关键规则靠 memory.md
```

## 九、默认 Agent 与 Skill 体系

### 1. 默认 Agent

系统初始默认提供四类高频角色：

- `Frontend Engineer`
- `Backend Engineer`
- `Product Manager`
- `System Architect`

### 2. Skill 绑定思路

每个 Agent 可以绑定不同 Skill，以形成稳定的角色能力边界。

例如：

- `Frontend Engineer`
  - 组件设计
  - 页面改造
  - 样式与交互实现
  - 前端工程化检查

- `Backend Engineer`
  - API 设计
  - 数据模型调整
  - 服务实现
  - 后端测试与调试

- `Product Manager`
  - 需求拆解
  - 用户故事整理
  - 优先级分析
  - 验收标准生成

- `System Architect`
  - 模块划分
  - 技术选型建议
  - 架构风险分析
  - 长期演进建议

### 3. 自定义 Agent 与 Agent Framework

系统除了默认 Agent 外，还应支持用户创建自定义 Agent。

在创建自定义 Agent 时，除了配置角色提示词、权限和 Skill，还应允许用户选择该 Agent 所使用的 `Agent Framework`。

对于编程型 Agent，平台应优先支持通过适配器方式接入外部 Agent Framework，例如：

- `Claude Code Adapter`
- `Codex Adapter`

这里的“框架选择”本质上决定的是：

- 该 Agent 后续主要使用哪套编程执行环境
- 采用哪种工具调用风格
- 采用哪种任务循环和代码修改工作流

也就是说，Agent 的能力不只由角色提示词决定，还由其所接入的 `Agent Framework` 决定。

在这一层里，`AgentHub` 负责统一的编排、上下文注入、结果回收和状态跟踪，而 `Claude Code` / `Codex` 这类外部 Agent Framework 负责具体的编程执行循环。

至于底层模型是否可配置，不应在平台层强行假设统一能力，而应遵循一条原则：

- **模型配置按框架能力决定**

因此自定义 Agent 至少应包含以下几个配置维度：

- 角色身份
- 提示词
- Skill 集合
- 权限边界
- `Agent Framework`
- 框架级配置项

这样系统里的 Agent 才能既支持统一编排，又允许不同 Agent 在实现层采用不同的工作模式。

### 4. Skill 的作用

Skill 不只是提示词模板，而应承担：

- 角色方法论约束
- 输出格式规范
- 风险检查项
- 特定领域的执行流程提示

这样默认 Agent 才不是“同一个模型换名字”，而是具有稳定行为差异的专业角色。

## 十、系统主流程

一条典型的多 Agent 协作主流程如下：

```text
用户进入单聊或群聊
-> 会话绑定 Workspace
-> 用户直接给某个 Agent 任务，或交给 Orchestrator
-> Orchestrator 生成当前 Plan
-> 选择一个或多个 Agent 执行当前任务
-> Agent 在 Sandbox 中工作
-> 产出 Proposal / 结果 / 解释
-> Orchestrator 检查并更新 Plan
-> 必要时通过 question tool 向用户提问
-> 必要时 redispatch 或 replan
-> 用户确认 Proposal
-> 更新 Version History
```

如果是普通单聊，则上面的流程中可以没有 `Orchestrator`，由单个 Agent 直接处理用户请求。

## 十一、MVP 落地建议

如果按 MVP 推进，建议优先实现下面四块：

### 1. 会话与边界

- 群聊
- 群内单聊
- 普通单聊
- 群聊主线程收口协作状态

### 2. Orchestrator 动态 Plan

- 基本任务拆解
- 任务状态推进
- 任务完成后自动检查
- `question tool` 介入式继续决策
- redispatch 与局部 replan

### 3. Workspace 工程闭环

- 会话挂载 Workspace
- Project Workspace 绑定
- Sandbox 执行
- Proposal Pool
- Confirm 后沉淀版本

### 4. 记忆 MVP

- 当前 session 中段压缩
- `mem0`
- `memory.md`

### 5. Agent 配置体系

- 默认 Agent
- Skill 绑定
- 自定义 Agent
- `Agent Framework` 选择
- 模型配置按框架能力决定

这些能力跑通后，AgentHub 就已经具备一个最小可用的多 Agent 工程协作闭环。

## 十二、一句话总结

AgentHub 的总体设计可以概括为：

- **以群聊/单聊作为统一协作入口，以带 `question tool` 的动态 Plan Orchestrator 作为多 Agent 主控，以 Workspace 作为工程落地边界，以 Compression + mem0 + memory.md 作为长会话连续性方案，并在系统中预置多个绑定不同 Skill、可接入不同 `Agent Framework`（如 `Claude Code Adapter`、`Codex Adapter`）且模型配置按框架能力决定的专业 Agent，形成一套既能自然对话、又能稳定承接真实工程协作的多 Agent 平台。**
