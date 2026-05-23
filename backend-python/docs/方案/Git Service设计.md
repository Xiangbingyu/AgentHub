# AgentHub Git Service 设计方案

## 1. 文档目标

本文档用于定义 `AgentHub` 中 `Git Service` 的 MVP 设计方案，重点回答以下问题：

- `Git Service` 在整体架构中的定位是什么
- MVP 阶段需要实现哪些能力
- `Git Service` 与 `Workspace`、`Project Workspace`、`Proposal Pool`、`Agent Sandbox` 的关系是什么
- 是否需要对外暴露接口，以及应该暴露哪些接口
- 第一版如何以最低复杂度落地

本文档默认继承现有 `Workspace` 方案中的基础概念，不重复展开聊天、权限和部署体系的全部细节。

---

## 2. 设计目标

`Git Service` 的核心目标不是把 Git 原生命令直接暴露给业务层，而是把 Git 作为 `Project Workspace` 的底层版本控制引擎，向上提供稳定的产品语义能力。

MVP 阶段重点实现以下目标：

- 为每个 `Project Workspace` 初始化并管理一个 Git 仓库
- 支持以 `Proposal Branch` 为核心的变更提交流程
- 支持 Agent 在 `Sandbox` 中提交改动并生成 Proposal
- 支持查看 Proposal 的 Diff、变更文件和状态
- 支持 `Confirm`，即把 Proposal 合并到项目主线
- 支持记录 `Version History`
- 支持在稳定版本形成后手动 `Push` 到远端仓库

---

## 3. 非目标

以下能力不属于 MVP 范围，后续再演进：

- 多节点分布式 Git 调度
- GitHub / GitLab / Gitea 深度集成
- 自动 rebase、自动冲突解决
- 多 Agent 同时维护同一 Proposal Branch，系统层面直接禁止
- 完整 CI/CD 流水线
- 复杂的分支保护策略
- 面向公网直接暴露原生 Git 命令

---

## 4. 整体定位

### 4.1 在架构中的位置

`Git Service` 是平台内部的版本控制控制面，负责统一管理：

- `Project Workspace` 对应的 Git 仓库
- `Proposal` 与 `Proposal Branch` 的映射关系
- `Sandbox` 与工作副本的绑定关系
- `Confirm`、`Push`、`Version History` 等关键动作

它不负责：

- 聊天消息流转
- Agent 推理
- 直接替代 Sandbox 改代码
- 直接执行部署

### 4.2 一句话定义

`Git Service` 是平台内部的 Git 编排层，负责将项目级的版本控制动作，从产品语义映射为底层仓库、分支、提交、合并和远端同步操作。

---

## 5. 与现有分层的关系

### 5.1 Workspace

- `Workspace` 是协作空间和持久化边界
- `Git Service` 不直接挂在 `Workspace` 总层
- 它只在 `Workspace` 下的具体 `Project Workspace` 上发挥作用

### 5.2 Project Workspace

- `Project Workspace` 是 `Git Service` 的主锚点
- 一个 `Project Workspace` 默认绑定一个 Git 仓库
- 该仓库的主分支用于承载项目真源

### 5.3 Proposal Pool

- `Proposal Pool` 是产品层的提案列表
- `Git Service` 负责将单个 `Proposal` 映射为对应的 `Proposal Branch`
- `Proposal Pool` 本身不直接执行 Git 命令，但依赖 `Git Service` 提供 Diff、状态和合并结果

### 5.4 Agent Sandbox

- `Sandbox` 是临时工作副本
- Agent 的改动实际发生在 `Sandbox` 的工作目录中
- `Git Service` 需要知道某个 `Sandbox` 当前绑定哪个项目、哪个分支、哪个工作目录

### 5.5 Execution Environment

- `Execution Environment` 承载实际的 Git 命令执行环境
- MVP 阶段可先采用一种统一的代码执行环境模板，并在其中预置 Git
- `Git Service` 本身不保存 Git 进程，而是调度对应工作目录上的 Git 操作

---

## 6. MVP 设计原则

### 6.1 单机优先

第一版优先采用单机或共享磁盘方案：

- 仓库和 Sandbox 工作目录都在后端可访问路径中
- `Git Service` 可直接在目标工作目录上执行 Git 命令
- 暂不引入远程执行代理

### 6.2 Proposal Branch 优先

- 每个 `Proposal` 对应一个独立分支
- Agent 不允许直接在 `main` 上修改
- 所有代码写回都经过 `Proposal -> Confirm` 流程
- 同一时刻，一个 `Proposal Branch` 只能由一个 Agent 负责维护

### 6.3 Branch Lock 优先

- 系统为每个 `Proposal Branch` 建立独占写锁
- 一个分支同一时刻只能绑定一个可写 Agent
- 未持有写锁的 Agent 只能查看 Proposal 信息，不能直接向该分支提交改动
- 如果其他 Agent 需要参与实现，应创建新的 Proposal Branch，而不是共写同一分支

### 6.4 语义接口优先

上层调用的是：

- 创建 Proposal
- 提交改动
- 查看 Diff
- 确认合并
- Push 项目

而不是直接使用：

- `git add`
- `git commit`
- `git merge`
- `git push`

### 6.5 Confirm、Push、Deploy 分离

- `Confirm` = 合并 Proposal 到项目主线
- `Push` = 将稳定版本同步到远端仓库
- `Deploy` = 将已确认版本发布到运行环境

这三者必须在系统层面分开建模。

---

## 7. MVP 功能范围

MVP 阶段的 `Git Service` 需要实现以下功能。

### 7.1 仓库初始化

- 为某个 `Project Workspace` 创建本地仓库
- 初始化默认分支 `main`
- 可选绑定一个远端仓库地址

### 7.2 Proposal Branch 创建

- 从 `main` 或指定基线分支创建 Proposal Branch
- 建立 `Proposal <-> Branch` 映射关系
- 创建分支后自动为当前负责 Agent 创建 `Branch Lock`

### 7.3 Sandbox 绑定

- 记录某个 `Sandbox` 当前对应的：
  - `project_id`
  - `repo_id`
  - `branch_name`
  - `working_dir`
- 记录当前 Sandbox 是否为该分支的持锁执行环境

### 7.4 提交改动

- 在目标 `Sandbox` 工作目录中执行：
  - `git status`
  - `git add`
  - `git commit`
- 返回最新 `head commit`
- 提交前必须先通过 `Branch Lock` 校验

### 7.5 Diff 查询

- 获取 Proposal Branch 相对于主线的 diff
- 获取 changed files 列表
- 获取 commit 摘要

### 7.6 Confirm 合并

- 校验 Proposal 是否可合并
- 执行 merge 或 squash merge
- 将结果写入项目主线
- 生成版本记录

### 7.7 Push 远端同步

- 手动触发主线 `push`
- 作为显式动作，不默认自动触发

### 7.8 历史记录

- 查询项目主线的版本记录
- 查询由哪个 Proposal 产生了哪个版本

---

## 8. MVP 不做什么

为了控制复杂度，以下能力不建议第一版实现：

- 自动解决 merge conflict
- 多 Sandbox 实时分支同步
- Agent 直接对远端仓库写入
- 复杂的 tag / release 流程
- Proposal 自动联动测试编排
- 细粒度 commit 编辑和 amend 管理

---

## 9. 核心对象设计

### 9.1 Repository

表示一个 `Project Workspace` 绑定的 Git 仓库。

建议字段：

- `repo_id`
- `project_id`
- `local_path`
- `default_branch`
- `remote_url`
- `created_at`

### 9.2 Proposal

表示一次独立的变更提案。

建议字段：

- `proposal_id`
- `project_id`
- `repo_id`
- `title`
- `branch_name`
- `base_branch`
- `base_commit`
- `head_commit`
- `status`
- `created_by_agent`
- `created_at`

推荐状态：

- `draft`
- `ready_for_review`
- `merged`
- `rejected`

### 9.3 SandboxBinding

表示某个 `Sandbox` 与某个 Git 工作副本的绑定关系。

建议字段：

- `sandbox_id`
- `project_id`
- `repo_id`
- `branch_name`
- `working_dir`
- `base_commit`
- `head_commit`
- `status`

### 9.4 VersionRecord

表示一次确认合并后的项目版本记录。

建议字段：

- `version_id`
- `project_id`
- `commit_hash`
- `source_proposal_id`
- `created_at`
- `created_by`

### 9.5 BranchLock

表示某个 `Proposal Branch` 的独占写锁。

建议字段：

- `lock_id`
- `project_id`
- `proposal_id`
- `repo_id`
- `branch_name`
- `agent_id`
- `sandbox_id`
- `status`
- `locked_at`
- `released_at`

推荐状态：

- `locked`
- `released`
- `merged`
- `closed`

---

## 10. 模块职责拆分

MVP 阶段可以先实现为一个后端内部模块 `GitService`，内部再按职责组织方法。

### 10.1 RepositoryManager

负责：

- 初始化仓库
- 读取仓库路径和默认分支
- 绑定远端地址

### 10.2 BranchManager

负责：

- 创建 Proposal Branch
- 查询分支状态
- 删除已归档分支

### 10.3 WorkingCopyManager

负责：

- 维护 Sandbox 与分支绑定
- 获取工作目录路径
- 查询当前工作副本状态

### 10.4 DiffManager

负责：

- 获取 diff
- 获取 changed files
- 获取 commit 摘要

### 10.5 MergeManager

负责：

- 校验可合并性
- 执行 `Confirm`
- 写入 `VersionRecord`

### 10.6 BranchLockManager

负责：

- 为新建 Proposal Branch 创建独占写锁
- 校验某个 Agent / Sandbox 是否拥有当前分支的写权限
- 在 Proposal 不再继续维护时释放锁
- 拒绝其他 Agent 对已加锁分支的写入请求

---

## 11. 核心方法设计

MVP 阶段建议至少提供以下内部方法：

### 11.1 仓库管理

- `initRepository(projectId, localPath, remoteUrl?)`
- `getRepository(projectId)`

### 11.2 Proposal / 分支管理

- `createProposalBranch(projectId, proposalId, baseBranch = "main")`
- `getProposalBranch(proposalId)`

### 11.3 Sandbox 绑定

- `bindSandbox(sandboxId, projectId, repoId, branchName, workingDir)`
- `getSandboxBinding(sandboxId)`

### 11.4 Branch Lock

- `createBranchLock(projectId, proposalId, repoId, branchName, agentId, sandboxId)`
- `getBranchLock(branchName)`
- `checkBranchLock(branchName, agentId, sandboxId)`
- `releaseBranchLock(proposalId)`

### 11.5 提交与变更

- `getWorkingCopyStatus(sandboxId)`
- `commitChanges(sandboxId, message)`
- `getProposalDiff(proposalId)`
- `getChangedFiles(proposalId)`

### 11.6 合并与历史

- `confirmProposal(proposalId, strategy = "squash")`
- `getProjectHistory(projectId)`

### 11.7 远端同步

- `pushProject(projectId, branch = "main")`

---

## 12. 是否需要暴露为接口

需要，但建议分两层。

### 12.1 内部接口

这是必须的。

`Git Service` 需要向后端内部其他模块暴露能力，例如：

- `Project Service`
- `Sandbox Service`
- `Proposal Service`
- `Deploy Service`

这一层可以先用内部 service 方法实现，不一定一开始拆成 HTTP 服务。

### 12.2 业务 API

建议有，但应暴露产品语义接口，而不是 Git 原生命令。

推荐的业务接口如下：

#### 项目仓库初始化

- `POST /projects/{id}/repo/init`

#### 创建 Proposal

- `POST /projects/{id}/proposals`

#### 查询 Proposal Pool

- `GET /projects/{id}/proposals`

#### 查询 Proposal Diff

- `GET /proposals/{id}/diff`

#### 提交当前改动

- `POST /proposals/{id}/commit`

#### Confirm 合并

- `POST /proposals/{id}/confirm`

#### Push 项目主线

- `POST /projects/{id}/push`

#### 查询历史版本

- `GET /projects/{id}/history`

### 12.3 不建议直接暴露的接口

MVP 阶段不建议直接对前端开放：

- `git add`
- `git checkout`
- `git merge`
- `git push`
- `git reset`

原因是：

- 容易破坏产品语义一致性
- 不利于权限控制
- 容易造成误操作

---

## 13. 一次标准流程

下面是一条最小可用的 Git Service 工作流：

1. 用户在某个 `Workspace` 下创建 `Project Workspace`
2. `Project Service` 调用 `Git Service.initRepository()`
3. 系统为某个 Agent 创建 `Sandbox`
4. `Proposal Service` 创建一个 Proposal
5. `Git Service.createProposalBranch()` 从 `main` 切出 Proposal Branch
6. `Git Service.createBranchLock()` 为当前 Agent 创建该分支的独占写锁
7. `Git Service.bindSandbox()` 将 Sandbox 绑定到该 Proposal Branch
8. Agent 在 Sandbox 中修改代码
9. 上层调用 `Git Service.commitChanges(sandboxId, message)`，提交前先校验写锁
10. 用户在 Proposal Pool 中查看 `Git Service.getProposalDiff(proposalId)` 的结果
11. 用户点击 `Confirm`
12. 上层调用 `Git Service.confirmProposal(proposalId)`
13. 系统 merge 到主线，并生成 `VersionRecord`
14. Proposal 完成后释放该 `Branch Lock`
15. 用户在需要时手动调用 `Git Service.pushProject(projectId)`

---

## 14. 运行方式建议

### 14.1 MVP 方案

第一版建议采用以下实现方式：

- `Git Service` 作为后端内部模块存在
- Git 仓库存放在后端本地磁盘或共享磁盘
- Sandbox 工作目录对后端可见
- `Git Service` 直接在目标工作目录执行 Git 命令

这种方式的优点：

- 实现简单
- 调试方便
- 足够支撑比赛和 MVP 演示

### 14.2 后续演进方向

后续可逐步演进为：

- `Git Service` 只做控制面
- `Runtime Executor` 在具体执行环境中执行命令
- 支持容器、远程沙箱和多节点执行

---

## 15. 安全与约束

MVP 阶段建议至少落实以下约束：

- 禁止 Agent 直接在 `main` 上提交
- 所有改动必须先进入 `Proposal Branch`
- 同一 `Proposal Branch` 同一时刻只能由一个 Agent 持有写权限
- 未持有 `Branch Lock` 的 Agent 不允许向该分支提交改动
- `Confirm` 前必须检查 Proposal 是否仍然可合并
- `Push` 必须为显式动作，不随每次 `Confirm` 自动触发
- Git 凭证由系统托管，不直接暴露给 Agent
- 所有 `branch`、`commit`、`confirm`、`push` 操作必须留审计记录

---

## 16. MVP 成功标准

满足以下条件，即可认为 MVP 版本的 `Git Service` 已经成立：

- 能为项目初始化 Git 仓库
- 能为 Proposal 创建独立分支
- 能让 Agent 在 Sandbox 中提交改动
- 能在 Proposal Pool 中查看 diff 和变更文件
- 能执行 Confirm 并合并到主线
- 能生成版本记录
- 能在稳定阶段手动 push

---

## 17. 一句话总结

MVP 版 `Git Service` 不需要一开始就做成复杂的独立微服务，它首先应该是一个后端内部的 Git 编排模块，围绕 `Project Workspace` 提供仓库初始化、Proposal Branch、提交、Diff、Confirm、Push 和版本记录这几项核心能力，并通过产品语义接口支撑 `AgentHub` 的协作开发流程。
