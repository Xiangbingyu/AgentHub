# AgentHub Workspace 方案

## 方案概述

目标很简单：把“聊天”和“工程落地”分开。

- 聊天只负责沟通、拆解、汇报
- Workspace 负责项目边界和权限
- Sandbox 负责实际执行
- Proposal 负责变更审阅
- Git 负责版本控制

只有挂载 Workspace 后，Agent 才进入代码协作态。

---

## 核心结构

### 1. Workspace

用户手动创建的顶层协作空间，用来承载个人开发或多人共创的项目边界。

### 2. Project Workspace

Workspace 下的项目级工作区，承载源码、配置、Proposal 和版本历史。接入 Git 后，它对应一个 Git Repository。

### 3. Proposal Pool

项目级待审阅变更池，用来汇总多个 Agent 产出的 diff、测试结果、预览链接和风险说明。

### 4. Agent Sandbox

Agent 的临时执行环境，用于编码、测试、构建和预览。它基于项目快照创建，任务结束后销毁。

### 5. Version History

Proposal 被确认后形成的版本记录，用于回看、审计和回滚。

---

## 关键原则

- 沟通与落地分离
- 执行与持久化分离
- 协作与权限分离
- 修改先进入 Proposal，再决定是否合并
- Git 只放在项目层，不放在聊天层

---

## 会话流程

1. 创建聊天
2. 挂载 Workspace
3. 绑定 Project Workspace
4. 创建 Agent Sandbox
5. 进入代码协作态

未挂载 Workspace 时，聊天只能用于需求讨论和结果汇报，不能直接改项目文件。

---

## Proposal 落地流程

1. `Project Workspace` 提供项目真源快照
2. `Agent Sandbox` 在隔离环境中编写代码、跑测试、产出预览
3. `Proposal Pool` 汇总变更信息
4. 用户或 Orchestrator 审阅后执行 `Confirm`，即 merge 回主线
5. 更新 `Version History`

这套流程的好处是：

- 多个 Agent 并行时不会直接污染主线
- 所有修改都有审阅入口
- 天然适合映射到 Git 分支与合并

---

## 单聊与群聊

### 单聊

- 先选 Workspace，再进入协作
- 适合个人开发或个人委派
- 一个会话只绑定一个 Workspace

### 群聊

- 群聊进入共创前也要绑定 Workspace
- 所有成员和 Agent 的产出统一落在同一项目空间
- Workspace 切换建议由管理员控制

---

## 规则摘要

| 规则 | 说明 |
| --- | --- |
| Workspace 手动创建 | 支持多个独立项目域 |
| 聊天需挂载 Workspace | 避免讨论直接污染项目真源 |
| 一个会话只绑定一个 Workspace | 保持上下文清晰 |
| 切换 Workspace 清空执行态 | 避免项目串扰 |
| Agent 只访问授权的 Project Workspace | 最小权限原则 |
| 修改先走 Proposal | 提升可追溯性和并发安全 |
| Sandbox 短生命周期 | 减少脏状态和环境污染 |
| Confirm / Push / Deploy 分离 | 避免把合并、同步、发布混成一个动作 |

---

## Git 接入

推荐方案是：每个 Proposal 对应一个独立分支。

- `Project Workspace` 绑定一个 Git Repository
- `Proposal Branch` 用来承载一次独立变更
- `Sandbox` 在分支上工作，允许多次 commit
- `Confirm` 表示 merge 回主线
- `Push` 表示同步远端
- `Deploy` 表示发布到运行环境

简化链路：

```text
Main Branch -> Proposal Branch -> Confirm -> Push -> Deploy
```

---

## 推荐流程

1. 创建群聊
2. 绑定 Workspace
3. 创建 Project Workspace 并初始化 Git 仓库
4. Agent 在 Sandbox 中基于 Proposal Branch 开发
5. 产出进入 Proposal Pool
6. 审阅后 Confirm 合并
7. 更新版本历史
8. 需要时再 Push 和 Deploy

---

## 一句话总结

AgentHub 的 Workspace 方案，就是用“Workspace + Sandbox + Proposal + Git”把聊天协作变成可落地、可审阅、可回滚的工程流程。
