# MCP 与 Skills Runtime 设计

## 概述

当前 agent 主链路已经收敛为单一 `internal_llm` 执行模式，所有能力通过 runtime tools 暴露给模型使用。下一阶段需要在这套架构上继续接入两类能力：

- `MCP`：远端或本地启动的外部 tool provider
- `skills`：可按需加载的系统化指令资产

本设计的核心原则是：

- `tools`、`mcp`、`skills` 作为三类独立资产分别管理
- 三者在同一条 runtime capability 链路中汇合
- agent 仍只通过内部 LLM + tool loop 工作
- `skills` 通过统一 `skill_tool` 加载，不将每个 skill 建成独立 tool
- `mcp` 保持独立资产与连接生命周期，但其导出的能力在运行时表现为普通 tools
- 不迁移现有 `tools` 目录，在现有主链路上最小化接入 `mcp` 与 `skills`

这允许系统在保持清晰边界的前提下，让模型获得统一的能力使用方式。

## 目标

- 为系统增加独立的 `mcp` 资产模块与 `skills` 资产模块。
- 保持 `tools`、`mcp`、`skills` 目录边界清晰，不强行混并资产层。
- 在运行时将内建 tools、`skill_tool`、MCP tools 合并到统一 `tool_registry`。
- 支持系统内置 skills。
- 支持系统内置 MCP server 定义或 preset。
- 保持 `executor_config` 只描述 internal LLM，不重新引入 executor mode 切换。
- 尽量复用当前 `RuntimeAssembler -> ToolResolver -> ToolRegistry -> InternalLlmExecutor` 主链路。

## 非目标

- 不将每个 skill 单独建成一个模型可见 tool。
- 不在本阶段引入新的 agent executor 类型。
- 不在本阶段把 MCP prompts/resources 强制并入主链路。
- 不在本阶段实现完整的远端 skill 拉取、版本同步、发布系统。
- 不为 `mcp`、`skills`、`tools` 引入过度抽象的统一 `CapabilityProvider` 框架。

## 设计结论

### 总体结论

采用“资产分开，运行时汇合”的结构：

- `tools` 管理本地内建工具与 tool registry。
- `mcp` 管理 MCP server 配置、连接、鉴权、tool discovery 与适配。
- `skills` 管理 skill 资产发现、内置 skill、内容装载与格式化。

运行时由 `RuntimeAssembler` 组装：

- tool config
- executor config
- skill registry
- MCP runtime
- unified tool registry

最终对模型暴露的是同一组 tools：

- 本地 built-in tools
- `skill_tool`
- 动态 MCP tools

### 为什么不把 MCP 资产并入 tools

虽然 MCP 最终表现成 tool，但它在资产层面具有 tool 本地实现不具备的职责：

- server 配置
- connection lifecycle
- auth
- tool discovery
- per-server timeout / headers / command
- 后续 prompts/resources 扩展

因此将 MCP 资产完全并入 `tools/` 会弱化目录语义，并让本地工具实现与远端 provider 生命周期耦合。

### 为什么 skills 通过 `skill_tool` 加载

skill 的本质不是“执行一个业务动作”，而是“为当前任务装载一套额外工作方法和约束”。

如果将每个 skill 建成单独 tool，会带来以下问题：

- tool 数量快速膨胀
- tool schema 与描述高度重复
- skill 动态发现很难映射到稳定 tool 标识
- skill 权限与来源管理复杂度上升

因此本设计采用单一 `skill_tool(name=...)` 作为统一加载入口。模型可见的是可用 skill 列表，真正需要时再加载对应 skill 正文。

## 目录结构

本设计不迁移现有 `tools` 目录，而是在现有项目结构上最小增加两个模块：

```text
app/
  tools/
  runtime/tools/
  runtime/mcp/
  runtime/skills/
  mcp/
    service.py
  skills/
    registry.py
```

目录职责：

- `app/tools/`
  - 保持现有 built-in tools 与 external code tools 实现
  - 只做必要最小修改，例如新增 `skill_tool`
- `app/runtime/tools/`
  - 保持现有 `ToolResolver`、`ToolRegistry` 主链路
  - 增加 MCP tools 与 `skill_tool` 的接入点
- `app/runtime/mcp/`
  - 放 MCP runtime 装配相关逻辑
  - 负责将 `app/mcp/service.py` 接入单次 run
- `app/runtime/skills/`
  - 放 skills runtime 装配相关逻辑
  - 负责将 `app/skills/registry.py` 接入单次 run
- `app/mcp/service.py`
  - 管理 MCP server 配置、连接、拉取工具、远端调用
- `app/skills/registry.py`
  - 管理 built-in skills、workspace skills、按名读取与摘要输出

不在本阶段新增以下文件：

- `specs.py`
- `models.py`
- `client.py`
- `discovery.py`
- `formatter.py`

原因不是这些概念永远不需要，而是当前阶段应优先做最小可落地实现，避免预留式拆分。

### 变更原则

本次实施按“现有链路最小扰动、功能增量接入”推进：

1. 保持现有 `app/tools/` 与 `app/runtime/tools/` 结构不动
2. 在 `app/runtime/mcp/` 与 `app/runtime/skills/` 下增加最小 runtime 接入层
3. 引入最小 `app/mcp/service.py`
4. 引入最小 `app/skills/registry.py`

这意味着第一目标不是迁移现有 tools，而是在统一 runtime 结构的前提下，不打断已稳定 tool 主链路地完成 MCP 与 skills 接入。

## 核心运行时模型

### Tool Assets

本地内建工具继续保留现有语义：

- `plan_tool`
- `delegate_tool`
- `code_tool`
- `bash_tool`
- `claude_code_tool`
- `opencode_tool`
- `question_tool`
- `skill_tool`

这些工具由本地代码实现，继续保留在现有 `app/tools/` 下，并直接注册进 `tool_registry`。

### Skill Assets

skill 资产包含：

- `name`
- `description`
- `location`
- `content`
- 可选 metadata

来源分三类：

- built-in skills
- workspace-local skills
- optional global skills

skill 资产本身不直接注册为 tool，而是由 `skill_tool` 负责按名称装载。

在最小实现阶段，skill 的发现、索引、摘要输出都先集中在 `skills/registry.py` 中，不再额外拆出 `discovery.py` 或 `formatter.py`。

### MCP Assets

MCP 资产包含：

- server identity
- type: `local` or `remote`
- local command / env
- remote url / headers
- timeout
- enabled flag
- optional auth config
- optional built-in preset defaults

MCP 资产由 `app/mcp/service.py` 管理连接与 tool discovery，连接成功后动态导出 MCP tools。

在最小实现阶段，不单独引入 `models.py`、`client.py`、`registry.py`。相关结构先保留在 `service.py` 内部，待复杂度确实上升后再拆分。

## 配置模型

### 总体原则

- `executor_config` 只描述 internal LLM
- `tool_config` 只描述模型可见工具入口与 runtime 执行开关
- `skill_config` 描述有哪些 skill 资产可被发现和加载
- `mcp_config` 描述哪些 MCP server 会接入当前 runtime

### Tool Config

保留当前 `tool_config` 主体，并增加 `skill_tool` 作为显式可配置工具。

建议语义：

```python
tool_config = {
    "tools": [
        {"name": "plan_tool", "enabled": True, "options": {}},
        {"name": "delegate_tool", "enabled": True, "options": {}},
        {"name": "bash_tool", "enabled": True, "options": {}},
        {"name": "skill_tool", "enabled": True, "options": {}},
    ],
    "auto_tool_choice": False,
    "model_tools_enabled": True,
    "runtime_tools_enabled": True,
    "command_policies": {"bash": {"*": "allow"}},
}
```

### Skill Config

新增结构化 `skill_config`：

```python
skill_config = {
    "builtins_enabled": True,
    "paths": [],
    "include_global": False,
    "allowed_skills": [],
}
```

语义：

- `builtins_enabled=True` 时自动加载系统内置 skills
- `paths` 允许附加项目级 skill 目录
- `include_global` 控制是否包含用户级全局 skill
- `allowed_skills` 可作为白名单过滤；为空表示不过滤

### MCP Config

新增结构化 `mcp_config`：

```python
mcp_config = {
    "enabled": True,
    "servers": [
        {
            "name": "github",
            "enabled": True,
            "type": "remote",
            "preset": "github",
            "url": "https://example.com/mcp",
            "headers": {},
            "timeout_seconds": 30,
        }
    ],
}
```

语义：

- `enabled=False` 时整个 MCP runtime 关闭
- `servers` 是当前 agent/runtime 显式启用的 MCP server 清单
- server 可引用 built-in preset，再叠加局部 override

### Agent Model 变化

建议在 `AgentModel` 上增加：

```python
skill_config: AgentSkillConfig = Field(default_factory=AgentSkillConfig)
mcp_config: AgentMcpConfig = Field(default_factory=AgentMcpConfig)
```

要求：

- 不把 `skill_config` 和 `mcp_config` 塞回 `prompt_policy`
- 不把 `mcp_config` 混进 `tool_config.options`
- 不把 `mcp`、`skill` 的资产级配置塞进 `executor_config`

## Runtime 组装流程

### RuntimeAssembler 责任扩展

`RuntimeAssembler` 在当前基础上扩展为：

1. 解析 runtime snapshot
2. 解析 `workspace_root`
3. 解析 `executor_config`
4. 解析 `prompt_policy`
5. 解析 `tool_config`
6. 调用 `runtime/skills/` 下的 resolver 构建 `skill_registry`
7. 调用 `runtime/mcp/` 下的 resolver 构建 `mcp_runtime`
8. 解析 `skill_config`
9. 解析 `mcp_config`
10. 交给现有 `ToolResolver` 汇总 tool registry

### RuntimeBundle 新字段

建议在 `RuntimeBundle` 增加：

- `skill_config`
- `mcp_config`
- `skill_registry`
- `mcp_runtime`

其中：

- `skill_registry` 提供可用 skill 列表与按名读取能力
- `mcp_runtime` 提供当前连接状态与动态 tool definitions

### Runtime 子目录职责

建议新增两个轻量 runtime 子目录：

- `app/runtime/mcp/`
- `app/runtime/skills/`

它们的职责只限于“当前这次 run 如何接入 MCP 与 skills”，不承载资产定义与核心业务逻辑。

建议最小文件形态：

```text
app/runtime/mcp/
  resolver.py

app/runtime/skills/
  resolver.py
```

职责约束：

- `app/runtime/mcp/resolver.py`
  - 从 runtime snapshot / agent config 读取 `mcp_config`
  - 调用 `app/mcp/service.py` 构建当前 run 的 `mcp_runtime`
- `app/runtime/skills/resolver.py`
  - 从 runtime snapshot / agent config 读取 `skill_config`
  - 调用 `app/skills/registry.py` 构建当前 run 的 `skill_registry`

不建议在 `app/runtime/mcp/` 或 `app/runtime/skills/` 中重复实现服务层逻辑。

### ToolResolver 变化

现有 `ToolResolver` 继续作为统一汇合点，但扩展两类来源：

1. built-in local tools
2. MCP-derived runtime tools

注册顺序建议为：

1. 注册 `tool_config.tools` 中声明的本地 built-in tools
2. 如果 `skill_tool` 启用，注册 `skill_tool`
3. 如果 `mcp_config.enabled` 为真，读取 `mcp_runtime` 中已连接的 MCP tools 并注册

这保证：

- 模型视角仍是一组普通 tools
- tool 来源保持可追踪
- MCP 不需要拥有独立执行主链

## Skill 设计

### Skill Registry

`app/skills/registry.py` 负责从以下来源搜集 skills：

- 内置 skills 定义位置
- workspace-local skill 目录
- optional global skill 目录
- `skill_config.paths` 中声明的额外目录

最小要求：

- 支持按名称唯一索引
- 忽略无效 skill 文件
- 对重名 skill 给出稳定覆盖规则

推荐覆盖规则：

- workspace skill 覆盖 built-in skill
- explicit path skill 覆盖 workspace skill
- global skill 优先级最低或默认关闭

提供接口：

- `all()`
- `available()`
- `get(name)`

并输出两种视图：

- system prompt 摘要视图
- `skill_tool` 装载全文视图

这部分逻辑先集中在同一个 `registry.py` 文件内，不额外拆 `discovery` 或 `formatter`。

### Built-in Skills

系统内置 skills 先以最小集合起步。推荐首批包括：

- 面向规划类任务的 skill
- 面向调试类任务的 skill
- 面向代码评审类任务的 skill
- 面向本系统配置编辑的 skill

要求：

- built-in skills 必须有稳定名称
- built-in skills 必须有简洁描述，便于模型选择
- built-in skills 内容必须可直接被 `skill_tool` 加载

### Skill Tool

新增 `skill_tool`，其职责是：

- 接收 skill 名称
- 从 `runtime.skill_registry` 中读取 skill
- 返回结构化文本块

输出建议包含：

- skill name
- description
- content
- location
- optional related files list

`skill_tool` 不直接执行副作用动作。它的作用是向当前对话注入额外工作方法。

### Prompt 注入

system prompt 中应注入 `available_skills` 摘要，而不是直接注入 skill 全文。

建议格式：

```text
Skills provide specialized instructions and workflows for specific tasks.
Use the skill tool to load a skill when a task matches its description.

<available_skills>
  <skill>
    <name>systematic-debugging</name>
    <description>Use when diagnosing failures or unexpected behavior</description>
  </skill>
</available_skills>
```

这样可以减少上下文膨胀，并保留按需加载语义。

## MCP 设计

### MCP Service

`app/mcp/service.py` 是 MCP 最小实现的核心文件。

本阶段最小支持两类 server：

- `local`
- `remote`

### Built-in MCP Presets

系统内置 MCP 不直接等于“自动启用的 server”，而是“可引用的预定义 server 资产”。

例如：

- `github`
- `jira`
- `docs_search`

配置时可以这样使用：

```python
{
    "name": "github-main",
    "preset": "github",
    "type": "remote",
    "enabled": True,
    "url": "https://example.com/github-mcp",
}
```

这样内置 MCP 的职责是提供默认 schema 和默认参数模板，而不是强制接入运行时。

`app/mcp/service.py` 负责：

- 读取 `mcp_config`
- 解析 built-in preset 与 override
- 连接 server
- 拉取 tool definitions
- 保存 connection status
- 将 MCP tool 转换为 runtime 可注册对象

最小接口建议：

- `connect_all()`
- `status()`
- `list_tools()`
- `get_tool_specs()`

这些接口先直接由 `service.py` 提供，不急于拆出独立 client、models 或 registry。

### MCP Tool Naming

MCP tool 名称必须稳定且避免冲突。

推荐格式：

- `<server_name>__<tool_name>`

示例：

- `github__search_issues`
- `jira__create_ticket`

不建议直接复用远端原始 tool 名，否则不同 server 间容易冲突。

### MCP Tool Adapter

`McpToolAdapter` 将远端 tool definition 转换为本系统 `ToolSpec`。

它负责：

- schema 适配
- request validation
- invoke 包装
- timeout 处理
- 错误归一化
- 返回文本结果或结构化结果摘要

### MCP 执行语义

对模型来说，MCP tool 与 built-in tool 没区别；对系统来说，执行路径不同：

- built-in tool：本地 Python 代码直接运行
- MCP tool：通过 `McpService` 远端调用

但两者都必须遵守 `ToolRegistry.dispatch(...)` 的统一调用约定。

## 权限与策略

### Skill 权限

建议为 skills 预留独立 permission namespace：

- `skill`

最小能力：

- allow
- deny
- ask

匹配对象为 skill 名称。

### MCP 权限

建议为 MCP tools 预留独立 permission namespace：

- `mcp`

也可细化为：

- 按 server 控制
- 按 tool name 控制

本阶段建议最小化为“按 server 或 tool id 模式匹配”。

### 与现有 command policy 的关系

`bash_tool` 的 command policy 继续只约束本地 shell 能力。
MCP 不复用 bash command policy。两者风险模型不同，应保持独立。

## 测试策略

### Skill 测试

至少覆盖：

- built-in skill discovery
- workspace skill discovery
- duplicate name 覆盖规则
- `skill_tool` 成功按名加载
- prompt 中 `available_skills` 摘要正确生成
- skill disabled / hidden 情况下不暴露给模型

### MCP 测试

至少覆盖：

- built-in MCP preset 解析
- local MCP server config 解析
- remote MCP server config 解析
- MCP tool naming 稳定性
- MCP tool definition 转换
- MCP tool invoke 成功路径
- MCP tool invoke 错误归一化
- MCP disabled 时不向 tool registry 注入任何动态 tool

### Runtime 装配测试

至少覆盖：

- `RuntimeAssembler` 正确构建 `skill_registry`
- `RuntimeAssembler` 正确构建 `mcp_runtime`
- `ToolResolver` 同时汇总 local tools、`skill_tool`、MCP tools
- orchestrator/worker 在不同 config 下拿到正确 tool 集

### E2E 测试

建议补充两类端到端：

- internal LLM 选择 `skill_tool` 后继续执行后续动作
- internal LLM 选择 MCP tool 完成远端能力调用

真实 MCP E2E 可以后置，但至少需要一个可控 fake MCP server 做稳定集成测试。

## 分阶段实施建议

### Phase 1: 保持现有 Tools 主链路稳定

- 不迁移 `app/tools/` 与 `app/runtime/tools/`
- 在现有 `ToolResolver` / `ToolRegistry` 上预留最小扩展点
- 建立统一的 `app/runtime/mcp/` 与 `app/runtime/skills/` 子目录结构
- 保证现有内建 tools、external code tools、bash tool、delegate chain 测试继续通过

### Phase 2: MCP 最小骨架

- 增加 `app/mcp/service.py`
- 增加 `app/runtime/mcp/resolver.py`
- 支持最小 `mcp_config`
- 支持静态或 fake MCP server 的 tool discovery
- 支持将 MCP tools 动态并入 `tool_registry`

### Phase 3: Skills 最小骨架

- 增加 `app/skills/registry.py`
- 增加 `app/runtime/skills/resolver.py`
- 支持 built-in skills
- 支持 workspace skills
- 在现有 `app/tools/` 下增加 `skill_tool`
- 在 prompt 中暴露 `available_skills`

### Phase 4: 增量验证与扩展

- 补齐 internal LLM E2E
- 视需要追加 auth、prompts、resources 扩展
- 复杂度上升后再考虑拆分 `models.py`、`client.py`、`formatter.py` 等文件

## 风险与缓解

### 风险 1：prompt 膨胀

如果直接注入全部 skill 正文或过多 MCP 描述，容易导致 context 无谓膨胀。

缓解：

- system prompt 仅注入 skill 摘要
- MCP 不做冗长说明，直接作为 tool defs 暴露

### 风险 2：MCP tool 不稳定

远端 server 可能超时、schema 异常、返回格式不稳定。

缓解：

- adapter 层统一错误处理
- timeout 可配置
- fake MCP server 测试先行

### 风险 3：skill 与 prompt policy 重复

如果 skill 内容和现有 prompt policy 重复，可能导致行为冲突。

缓解：

- skill 只负责额外任务方法，不复写基础 runtime 规则
- built-in skill 文案保持聚焦

### 风险 4：配置语义混乱

如果把 `tool_config`、`skill_config`、`mcp_config` 混用，后续维护成本会上升。

缓解：

- 明确每类配置的单一职责
- resolver 层按配置类型分开归一化

## 最终设计摘要

本设计采用以下最终形态：

- `tools`、`mcp`、`skills` 三类资产独立管理
- 保持现有 `app/tools/` 与 `app/runtime/tools/` 主链路不迁移
- `mcp` 先收缩为单一 `app/mcp/service.py`
- `skills` 先收缩为单一 `app/skills/registry.py`
- `runtime` 采用统一子目录：`app/runtime/mcp/` 与 `app/runtime/skills/`
- `mcp` 提供远端 tool provider 能力，并在运行时导出普通 tools
- `skills` 提供可按需加载的任务指令资产，并通过单一 `skill_tool` 接入
- `RuntimeAssembler` 负责构建 `skill_registry` 与 `mcp_runtime`
- 现有 `ToolResolver` 负责把 built-in local tools、`skill_tool`、MCP tools 汇总到统一 `tool_registry`
- `executor_config` 继续保持 internal-only

这套方案在不破坏现有 internal LLM tool loop 主链路的前提下，以最小目录增量接入 skill 与 MCP，并避免为目录统一先做一次无业务收益的迁移。
