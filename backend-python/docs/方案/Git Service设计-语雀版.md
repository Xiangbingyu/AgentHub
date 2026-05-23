# AgentHub Git Service 设计

这份文档先把 Git Service 本身拥有哪些内部服务能力讲清楚，再说明其中哪些能力会被封装成对外开放的业务接口，最后沿着一条主流程和一条查询流程讲清楚这套分层关系。

## 一、先看接口边界

这里先区分两层：

1. Git Service 自身提供的内部服务能力，供后端不同模块按需复用。
2. 从这些能力里挑出关键且稳定的一部分，再封装成前端或 Orchestrator 可直接调用的业务接口。

### 1. 开放接口

这部分是从内部能力里封装出的业务 API：

- `POST /projects/{id}/repo/init`
- `POST /projects/{id}/proposals`
- `GET /projects/{id}/proposals`
- `GET /proposals/{id}/diff`
- `POST /proposals/{id}/commit`
- `POST /proposals/{id}/confirm`
- `POST /projects/{id}/push`
- `GET /projects/{id}/history`

### 2. 内部接口

这部分是 Git Service 自身提供的内部服务：

- `initRepository(...)`
- `createProposalBranch(...)`
- `listProposals(...)`
- `getProposalDiff(...)`
- `getProjectHistory(...)`
- `bindSandbox(...)`
- `createBranchLock(...)`
- `checkBranchLock(...)`
- `getSandboxBinding(...)`
- `getWorkingCopyStatus(...)`
- `confirmProposal(...)`
- `pushProject(...)`

### 3. 这一层的核心理解

开放接口和内部接口不是两套彼此独立的能力。

更准确地说，Git Service 本体先提供一组可复用的内部服务，再由业务层把其中部分关键能力按产品语义封装成“创建 Proposal”“提交改动”“确认合并”“查看历史”这类对外动作。

这里列出的内部接口是核心子集，不是完整清单。尤其在读取场景下，一个开放接口往往会组合多个内部查询能力来完成。

## 二、开放接口

这一组接口是业务层真正会直接看到和使用的接口。它们不是 Git Service 的全部能力清单，而是从内部服务里挑出的关键动作，再补上鉴权、参数校验、幂等控制、审计记录等业务封装后形成的对外 API。

### 1. `POST /projects/{id}/repo/init`

用于初始化项目仓库。通常发生在项目第一次接入 Git 时，对外暴露的是这个业务接口，内部通常会在校验通过后调用 `initRepository(...)` 来创建 Repository、准备默认主线 `main` 并写入元数据。

### 2. `POST /projects/{id}/proposals`

用于创建一条新的 Proposal。除了生成提案记录，还会在内部编排里调用 `createProposalBranch(...)` 切出 Proposal Branch，并按需要补上 Sandbox 绑定和锁信息初始化。

### 3. `GET /projects/{id}/proposals`

用于查看当前项目下的 Proposal Pool，也就是当前项目里所有待审、待合并、已合并的提案列表。它对外表现为一个列表接口，但内部通常会以 `listProposals(...)` 为主入口，再组合提案状态、分支摘要、最近提交等查询能力，拼装出业务层需要的列表视图。

### 4. `GET /proposals/{id}/diff`

用于查看某个 Proposal 的具体变更内容，通常包括 changed files、diff 摘要以及对应的提交信息。它对外是评审视图，内部通常会以 `getProposalDiff(...)` 为主入口，再组合 changed files、commit range、diff patch 等仓库查询能力生成结果。

### 5. `POST /proposals/{id}/commit`

用于提交当前 Proposal Branch 上的一轮修改。它代表“把当前 Sandbox 里的改动正式记到这个 Proposal 里”；在内部通常会串起 `getSandboxBinding(...)`、`getWorkingCopyStatus(...)`、`checkBranchLock(...)` 等服务再完成提交。

### 6. `POST /proposals/{id}/confirm`

用于确认某个 Proposal，并把它合并进项目主线。对外看到的是 Confirm 这个业务动作，内部核心通常由 `confirmProposal(...)` 完成。这个动作对应的不是 Push，也不是 Deploy。

### 7. `POST /projects/{id}/push`

用于把当前项目的稳定主线同步到远端仓库。通常发生在若干 Proposal 已经 Confirm 后的阶段性稳定版本时，对外暴露为业务动作，内部则由 `pushProject(...)` 等能力完成真正的主线同步。

### 8. `GET /projects/{id}/history`

用于查看项目的 Version History，帮助用户回看历史版本、审计变更来源，并为后续回滚提供依据。内部通常会以 `getProjectHistory(...)` 为主入口，再组合版本记录、关联 Proposal、提交摘要等查询能力形成可展示历史。

### 9. 这一层的核心理解

这一组接口全都属于“业务语义接口”。

因此前端不需要理解底层的 Git add、checkout、merge，也不需要知道内部具体调用了哪些服务；它只需要理解 Proposal、Confirm、Push 这些产品动作即可。

反过来说，没有被封装出来的内部服务，并不代表它们不重要，只是它们暂时不直接对外开放。

同时也不要求每个开放接口都和单一内部接口一一对应。尤其列表、Diff、History 这类读接口，通常本来就是内部组合查询的结果。

## 三、内部接口

下面这些接口不是给前端直接调用的，而是 Git Service 自身提供的内部服务能力。它们既可以被对外开放的业务接口编排调用，也可以被其他后端模块、后台任务、恢复流程或运维流程按权限直接复用。

这里列的是核心子集，用来表达能力边界和主调用关系，并不是要把 Git Service 的全部内部方法逐个铺开。

### 1. `initRepository(projectId, localPath, remoteUrl?)`

内部初始化仓库的方法，用于创建本地仓库、准备默认分支和写入 Repository 元数据。它可以被 `POST /projects/{id}/repo/init` 这类开放接口调用，也可以被项目导入、仓库修复、环境恢复等内部流程复用。

### 2. `createProposalBranch(projectId, proposalId, baseBranch)`

内部创建 Proposal Branch 的方法，用于从主线或指定基线切出工作分支。它通常会被创建 Proposal 的开放接口调用，但本身首先是一项可复用的内部能力。

### 3. `listProposals(projectId, filters)`

内部读取 Proposal 列表的主查询能力，用于按项目、状态、时间等条件返回 Proposal Pool 的基础数据。对外的 `GET /projects/{id}/proposals` 往往会以它为入口，再组合其他摘要信息进行列表拼装。

### 4. `getProposalDiff(proposalId, options)`

内部读取 Proposal 变更详情的主查询能力，用于获取某个 Proposal 对应的 diff、changed files、提交区间等信息。对外的 `GET /proposals/{id}/diff` 一般会围绕它再补齐评审视图需要的数据。

### 5. `getProjectHistory(projectId, pagination)`

内部读取项目版本历史的主查询能力，用于按时间或分页返回版本记录、关联提案、提交摘要等数据。对外的 `GET /projects/{id}/history` 通常会基于它再整理出审计和回看所需的展示结构。

### 6. `bindSandbox(sandboxId, projectId, repoId, branchName, workingDir)`

内部绑定 Sandbox 的方法，用于记录某个 Sandbox 当前对应的仓库、分支和工作目录。它可以服务于创建 Proposal 后的初始化，也可以服务于会话恢复、Agent 迁移或故障恢复场景。

### 7. `createBranchLock(...)`

内部创建 Branch Lock 的方法，用于保证一个 Proposal Branch 同一时刻只能由一个 Agent 修改。它属于系统级约束能力，不一定需要单独对外暴露，但可以被多个内部流程共享调用。

### 8. `checkBranchLock(branchName, agentId, sandboxId)`

内部校验当前 Agent 和 Sandbox 是否持有目标分支写权限的接口，commit 前必须先经过这一层检查。除了提交流程，其他可能修改分支状态的内部流程也可以复用这层校验。

### 9. `getSandboxBinding(sandboxId)`

内部查询 Sandbox 绑定关系的接口，用于定位具体该在哪个工作目录执行 Git 操作。它更像基础查询能力，通常不会直接对前端开放，但会被多个写操作或诊断流程依赖。

### 10. `getWorkingCopyStatus(sandboxId)`

内部读取工作副本状态的接口，用于检查当前 Sandbox 中有哪些未提交改动。它既可服务于 commit 前检查，也可服务于自动诊断、脏工作区预警等内部场景。

### 11. `confirmProposal(proposalId, strategy)`

内部执行 Confirm 的核心能力，负责完成主线合并和版本记录写入。对外的 `POST /proposals/{id}/confirm` 通常只是把这个内部能力包装成了更稳定的业务动作。

### 12. `pushProject(projectId, branch)`

内部执行主线 push 的能力，用于把稳定版本同步到远端仓库。它可以被 `POST /projects/{id}/push` 调用，也可以被内部发布流水线或批量同步任务复用。

### 13. 这一层的核心理解

简单理解：Git Service 本体就是这组内部服务。开放接口只是其中一部分能力在业务层的“对外包装”，所以两者不是一一对照的重复罗列，而是“能力层”和“业务封装层”的关系。

写接口常常会调用少数几个核心写能力，读接口则更常见地表现为“一个对外接口对应一组内部查询能力的组合”。

## 四、主流程

下面按一条完整主流程来讲。你可以把它理解成：从“项目第一次接入 Git”开始，到“代码进入主线并推送远端”为止，业务层会调用哪些开放接口，而这些开放接口在 Git Service 内部又会进一步编排哪些服务能力。

### 第 1 步：项目初始化仓库

当某个 Project Workspace 创建完成后，业务层先调用 `POST /projects/{id}/repo/init`。这个开放接口在内部通常会封装调用 `initRepository(...)`，完成 Repository 创建、默认分支 `main` 初始化以及项目与仓库的绑定。

### 第 2 步：创建 Proposal 和分支

当用户准备开始一轮新改动时，系统调用 `POST /projects/{id}/proposals`。这一步不只是建一条提案记录，还会在内部调用 `createProposalBranch(...)` 从 `main` 切出 Proposal Branch，后续所有改动都发生在这个分支上。

### 第 3 步：给分支加独占写锁

Proposal Branch 建好以后，Git Service 会继续调用 `createBranchLock(...)` 创建 Branch Lock。它的含义非常直接：这个分支同一时刻只能由一个 Agent 修改。未持有锁的 Agent 可以看 Proposal 信息，但不能往这个分支提交代码。

### 第 4 步：把 Sandbox 绑定到分支

当前负责的 Agent 会在自己的 Sandbox 里打开这个 Proposal Branch 对应的工作副本。Git Service 需要通过 `bindSandbox(...)` 记录清楚：这个 Sandbox 现在绑定的是哪个项目、哪个仓库、哪个分支、哪个工作目录。

### 第 5 步：Agent 修改并提交

Agent 在 Sandbox 里写代码、改文档、调配置，完成一轮修改后调用 `POST /proposals/{id}/commit`。这时开放接口会在内部编排 `getSandboxBinding(...)`、`getWorkingCopyStatus(...)`、`checkBranchLock(...)` 等服务，确认当前 Agent 确实有权往这个 Proposal Branch 提交。

### 第 6 步：Proposal Pool 展示可审内容

提交以后，系统会把这次 Proposal 的 diff、changed files、commit 信息整理出来。前端通过 `GET /projects/{id}/proposals` 看 Proposal Pool，通过 `GET /proposals/{id}/diff` 查看单个 Proposal 的具体差异；在内部，这两类读取通常分别以 `listProposals(...)` 和 `getProposalDiff(...)` 为主入口，再补齐评审视图所需的数据。

### 第 7 步：审核后执行 Confirm

如果用户或 Orchestrator 认为 Proposal 没问题，就调用 `POST /proposals/{id}/confirm`。这个开放接口在内部会调用 `confirmProposal(...)`，把 Proposal Branch merge 到主线，并生成一条 Version History 记录。

### 第 8 步：形成历史版本

Proposal 一旦 Confirm 成功，系统就会把本次合并沉淀成版本记录。之后可以通过 `GET /projects/{id}/history` 回看项目历史、确认某次变更来自哪个 Proposal；对内则通常由 `getProjectHistory(...)` 负责拉取历史主数据并组织展示结构。

### 第 9 步：在稳定阶段手动 Push

Confirm 完成并不代表立刻推远端。只有当项目主线达到一个稳定状态后，才通过 `POST /projects/{id}/push` 触发同步；而真正把当前主线同步到远端仓库的，仍然是内部的 `pushProject(...)` 这类能力。

### 第 10 步：Push 之后才考虑部署

Git Service 到这里的职责基本结束。后续是否进入预览、测试或正式部署，是 Deploy 阶段的事，不和 Confirm、Push 混在一起。

## 五、查询流程

除了写入主流程，Proposal Pool、Diff、History 这三类读接口也需要单独讲清楚。它们同样是开放接口触发内部编排，只是内部更偏向组合查询，而不是执行写操作。

### 读流程 A：读取 Proposal Pool

当前端调用 `GET /projects/{id}/proposals` 时，业务层会先做鉴权和过滤条件整理，再进入 Git Service 的查询编排。内部通常先调用 `listProposals(...)` 取得 Proposal 基础列表，再按需要补齐分支摘要、最近提交、状态统计等信息，最后返回前端真正需要的 Proposal Pool 视图。

### 读流程 B：读取 Proposal Diff

当前端调用 `GET /proposals/{id}/diff` 时，业务层会进入 Proposal 详情查询流程。Git Service 内部通常以 `getProposalDiff(...)` 为主入口，再组合 changed files、commit range、patch 内容等仓库查询能力，形成评审页真正需要的 diff 结果。

### 读流程 C：读取 Project History

当前端调用 `GET /projects/{id}/history` 时，业务层会把分页、筛选、审计视角等需求带入 Git Service。内部通常先调用 `getProjectHistory(...)` 拉取历史记录主数据，再补齐关联 Proposal、版本摘要、提交来源等信息，最终生成面向产品的 Version History 视图。

### 这一层的核心理解

主流程里并不是“只用了开放接口没有调用内部接口”，而是为了讲清主路径，前面主要展开了写入链路。补上查询流程以后，可以更完整地看到：开放接口始终只是入口，真正落地仍然依赖 Git Service 的内部服务编排。

## 六、把设计细节放回流程里看

如果只按主流程看，下面这些规则就是你当前这套设计里最重要的细节点。

### 细节 1：Git 只挂在 Project Workspace 上

仓库不是挂在聊天上，也不是挂在 Workspace 总层上，而是挂在具体的 Project Workspace 上。这样每个项目才有自己的真源和主线。

### 细节 2：每个 Proposal 对应一个 Branch

Proposal Pool 里的一项 Proposal，本质上对应一个 Proposal Branch。Proposal Pool 是列表，Proposal 才是单项变更提案。

### 细节 3：Sandbox 不是一次 Commit

Sandbox 是工作副本，一个 Agent 可以在一个 Sandbox 里做多次修改、多次 commit，最终都归到当前 Proposal Branch 上。

### 细节 4：Branch Lock 不是装饰，是硬约束

未持有 Branch Lock 的 Agent 不允许向该分支提交改动。这意味着系统层面直接杜绝“多个 Agent 同时维护同一 Proposal Branch”。

### 细节 5：Commit、Confirm、Push 不是一回事

Commit 只是把当前工作副本里的改动提交到 Proposal Branch；Confirm 是把 Proposal Branch merge 到主线；Push 是把稳定主线同步到远端。

### 细节 6：接口只开放业务动作

前端不会直接调用 `git checkout` 或 `git merge`，而是调用“创建 Proposal”“查看 Diff”“Confirm 合并”“Push 项目”这类业务接口。开放接口描述的是产品动作，不是底层命令集合。

### 细节 7：开放接口只是内部能力的子集封装

Git Service 本身先提供 `initRepository(...)`、`createBranchLock(...)`、`getWorkingCopyStatus(...)` 这类内部服务。只有其中一部分关键且稳定的能力，会被进一步封装成对外 API；剩下的内部服务仍可供其他后端流程直接复用。

### 细节 8：内部接口清单是核心子集，不是完整枚举

文档里列出内部接口的目的，是帮助读者理解 Git Service 的主要能力域和调用关系，而不是穷举每一个 helper、查询函数或底层仓库操作。因此清单应该覆盖关键入口，但不必假装“内部只有这几个方法”。

### 细节 9：读接口通常比写接口更像组合查询

`GET /projects/{id}/proposals`、`GET /proposals/{id}/diff`、`GET /projects/{id}/history` 这类接口，对外看是单一 API，对内往往会组合多个查询能力和展示拼装步骤。因此它们有对应的主查询入口，但不必强行理解成单一内部方法的机械映射。
