- Workspace ：用户手动创建的顶层协作空间，可用于个人开发或多人共创，是项目、文件、Proposal、版本记录与执行上下文的持久化边界。聊天只有在挂载 Workspace 后，才能进入代码协作态；当会话切换 Workspace 时，需要清空当前 Workspace 部分的聊天内容与执行态上下文，避免不同工作区之间的上下文污染。

- Project Workspace ：Workspace 下某个项目的持久化工作区，本质上是一个项目目录或项目作用域，用来承载该项目的源码、配置、版本历史和项目级待确认变更；在接入 Git 后，Project Workspace 底层绑定一个 Git Repository，作为项目真源的版本控制引擎。

- Proposal Pool ：项目级的变更提案池，用于汇总多个 Agent 在各自 Sandbox 中产出的修改结果，例如 Diff、测试结果、预览链接和风险说明，等待用户或 Orchestrator 审阅与确认；在接入 Git 后，Proposal Pool 可映射为一组待确认的 Proposal Branch。

- Agent Sandbox ：某个 Agent 在某次会话或某个任务中的临时执行环境，通常基于对应 Project Workspace 的快照创建，用于写代码、运行命令、测试、构建和预览，不直接作为最终持久化真源；在接入 Git 后，Sandbox 本质上是基于某个基线提交 checkout 出来的临时工作副本。平台在云端应维护一个默认的基础 Sandbox Image，至少内置 git、基础 shell 与常用系统工具；每次创建 Sandbox 时，都基于该基础镜像拉起一个临时环境，可优先从缓存恢复，也可重新构建。Sandbox 默认是短生命周期资源，任务完成后应自动销毁，避免环境污染与状态残留。

- Execution Environment ：对底层执行载体的统一抽象，用来屏蔽本地环境、容器、远程沙箱、云开发环境等差异；Agent Sandbox 运行在某个具体的 Execution Environment 之上，并通过该环境执行 Git clone、checkout、diff、commit、merge 等底层命令。当 Sandbox 需要运行测试、构建或预览时，Execution Environment 应根据项目配置文件进一步准备项目级依赖环境，例如安装语言依赖、恢复缓存或直接切换到 Docker/容器化执行模式，再在当前环境中运行测试样例。

- Version History ：项目级版本记录层，用于在 Proposal 被确认并应用到 Project Workspace 后，保存一次可追溯的提交快照，支持历史回看、版本对比和必要时的回滚；在接入 Git 后，可直接映射为 Git 的 commit、merge、tag 等历史记录。

## 规则补充

- Workspace 创建规则：Workspace 不是账号注册后自动生成的唯一空间，而是由用户按需手动创建，可用于个人开发，也可用于多人共创。

- 聊天挂载规则：单聊或群聊默认只是沟通容器，只有在挂载 Workspace 后，Agent 才能进入代码协作态，执行文件读写、测试、构建、预览与 Proposal 提交。

- 非挂载会话规则：未挂载 Workspace 的聊天仍可用于需求讨论、方案设计、任务拆解、Diff 解释或结果汇报，但不直接落代码、不直接修改项目文件。

- 会话绑定规则：一个会话在任意时刻只应绑定一个 Workspace；会话中的代码、文件、Proposal、版本记录都归属于当前绑定的 Workspace。

- Workspace 切换规则：当会话切换到新的 Workspace 时，需要清空当前 Workspace 部分的聊天内容、临时文件引用与执行态上下文，避免不同项目之间的上下文污染与错误继承。

- 新建会话优先规则：对于已经进入开发态的会话，不建议频繁直接切换 Workspace；更稳妥的方式是基于目标 Workspace 新建一个会话，或从当前会话派生一个新会话。

- 权限边界规则：Workspace 是持久化边界，不等于所有 Agent 默认可见范围。Agent 默认只应访问当前会话所绑定 Workspace 内被授权的 Project Workspace。

- 群聊协作规则：群聊在进入共创模式前也必须绑定 Workspace；群成员与多个 Agent 的协作产出统一落在该 Workspace 下，避免文件落地到个人私有空间。

- 管理员切换规则：群聊中的 Workspace 切换应由管理员执行。第一版产品中可以约定群主默认具备该权限，但概念上应保留 Workspace Admin 这一角色，便于后续扩展多人管理。

- Proposal 提交流程规则：Agent 不直接把修改写入 Project Workspace 真源，而是先在 Sandbox 中生成 Proposal，进入 Proposal Pool，待用户或 Orchestrator 确认后再写回项目。

- Sandbox 运行环境规则：平台在云端维护默认基础镜像，Sandbox 创建时基于该镜像拉起临时环境；执行测试或构建时，再按项目配置补齐依赖环境，必要时直接进入 Docker/容器模式；任务结束后 Sandbox 自动销毁。

- 版本沉淀规则：每次 Proposal 被正式应用到 Project Workspace 后，都应生成一条可追溯的版本记录，供后续回看、对比、审计和必要时回滚。

## Git 接入设计

- Git 嵌入层级：Git 不直接挂在 Workspace 总层，而是嵌入在 Project Workspace 层，作为项目真源的底层版本控制引擎。

- 仓库绑定规则：每个 Project Workspace 默认绑定一个 Git Repository；一个项目对应一个仓库是最清晰的第一版方案。

- 分支策略规则：采用方案 A，即每个 Proposal 对应一个独立的 Proposal Branch。Agent 在自己的 Sandbox 中围绕该分支工作，避免直接污染项目主分支。

- Sandbox 与 Commit 关系：一个 Sandbox 不是一次 commit，而是一个临时工作副本。Agent 可以在一个 Sandbox 中进行多次本地 commit，最终整理为一个 Proposal。

- Sandbox 环境准备规则：平台应维护默认基础镜像，至少包含 git 与基础运行工具；Sandbox 创建时可从缓存恢复或重新构建，运行测试前再根据 `requirements.txt`、`package.json`、`Dockerfile` 等项目配置补齐依赖环境，必要时直接在容器中执行。

- Confirm 语义规则：Confirm 表示某个 Proposal 被审阅通过，并合并进入 Project Workspace 的主线分支；它更接近 merge，不等于 push，也不等于 deploy。

- Push 语义规则：push 是把当前项目主线同步到远端仓库的动作，通常发生在多个已确认 Proposal 组成一个稳定版本之后，而不是每次 Confirm 后立即执行。

- Deploy 语义规则：deploy 发生在代码已经确认并形成稳定版本之后，用于把该版本发布到预览环境、测试环境或生产环境；它应与 Confirm 和 push 分开定义。

- 推荐链路：Agent Sandbox -> Proposal Branch -> Proposal Pool -> Confirm（merge）-> Version History -> Push -> Deploy。

- 远端保护规则：在最终稳定版本确认之前，Proposal Branch 默认不进入正式远端主仓库；如确有需要，可先同步到平台内部暂存仓库，但不视为正式发布。
