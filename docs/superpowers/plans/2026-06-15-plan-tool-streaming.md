# 为链路接入 plan_tool:对话生成 plan + SSE 流式回放每一步

## 目标(用户原话拆解)
1. 通过与 agent 对话触发 plan 生成,plan 文件落到**当前 session workspace** 的 `.AgentHub/plans/` 下。
2. SSE 返回执行的每一步:**每一轮回复**、**每一轮工具调用**、**最终回复**。
3. 前端**时间线内联展示**这些步骤(已选定)。

## 现状(探查确认)
- ✅ orchestrator seed 已配 `plan_tool`(+ delegate/bash),工具循环最多 8 轮已在跑。
- ✅ plan_tool 已实现:写 PlanRepository + 渲染 markdown 到 `<workspace>/.AgentHub/plans/{run_id}.execution-plan.md`(`plan_tool.py:50-110`)。
- ✅ SSE 透传**任意** event_type(`session_read.py` /events 不按 scope 过滤;gateway 原样转发)。前端 `useSessionStream` 已 listen 一批类型。
- 🔴 **阻塞**:`workspace_root` 永远解析成全局 `TEST_WORKSPACE_PATH`(`workspace_resolver.py:14-21`)。run 带了 `workspace_id` 但从未映射成磁盘 `root_path`。→ plan 写错目录。
- 🔴 **缺失**:工具循环里每轮回复/工具调用/工具结果**一个事件都不 emit**(`agent_run_input_service.py:246-281`)。只有 run.started / 最终 reply / run.completed。
- 🔴 前端 `handleStreamEvent` 只认 3 种事件,其余丢弃;无工具调用气泡渲染。

---

## 改动方案

### A. 修 workspace 链路(按 workspace_id 查 root_path)— 后端
**文件**:`runtime/workspace/workspace_resolver.py` + `runtime/runtime_assembler.py`

- `RuntimeAssembler.assemble` 在调用 `workspace_resolver.resolve(snapshot)` 前,若 snapshot 无 `workspace_root`,用 `agent_run.workspace_id` 查 `SessionWorkspaceRepository.get_by_id(...)` 拿 `root_path` 注入 snapshot。
- 给 `RuntimeAssembler.__init__` 注入可选 `session_workspace_repository`(默认 `SessionWorkspaceRepository()`),保持依赖注入风格、测试可替换。
- `workspace_resolver` 保留 `TEST_WORKSPACE_PATH` 作为**兜底**(查不到 workspace 或测试场景),不破坏现有测试。
- 净效果:`runtime_bundle.workspace_root` = 该 session 的 `.AgentHub/session-workspaces/<uuid>/`,plan 文件落到 `<那目录>/.AgentHub/plans/`。

### B. 工具循环 emit 中间事件 — 后端
**文件**:`services/agent_run_input_service.py`(`_run_internal_orchestrator_tool_loop` + `input`)

新增 emit(全部 `event_scope="main_timeline"`,经 DomainEventEmitter,自动分配 sequence_no):

1. **每轮 agent 文字回复**:循环内若 `current_response.content` 非空 →
   emit `session.message.appended`,payload `{"role":"assistant","content":...}`。
   (复用现有消息类型,前端直接当气泡渲染,零前端改动即可见。)
2. **每次工具调用**:对 `current_response.tool_calls` 每个 →
   emit `agent.tool_call`,payload `{"tool_name":..., "tool_call_id":..., "arguments":<dict>}`。
3. **每个工具结果**:对 `tool_results`(dispatch 返回)每个 →
   emit `agent.tool_result`,payload `{"tool_name":..., "tool_call_id":..., "result":<dict/str>}`。
4. **plan 更新**:dispatch 结果里若有 `name=="plan_tool"` →
   emit `plan.updated`,payload 取 plan_tool 返回的 `{plan_id, file_path, summary, steps, status}`(从 PlanRepository.get_by_run_id 读完整 steps)。
5. 最终回复仍走现有 `_emit_agent_reply`(循环外,`input:95`)。

注入:`AgentRunInputService` 已能拿到 `domain_event_emitter`(确认其构造)。emit 需要 `session_id`/`session_workspace_id`/`run_id`——从 `runtime_bundle.agent_run` 取。

> 边界:循环里 LLM 多轮可能产生多条 assistant 文字,都会成为独立气泡——符合"每一轮回复"的要求。

### C. 前端时间线内联渲染 — frontend
**文件**:`hooks/useSessionStream.js`、`pages/Chat/Chat.jsx`、`components/ChatPanel/ChatPanel.jsx`(+ css)

1. `useSessionStream.js`:`eventTypes` 数组加 `'agent.tool_call'`、`'agent.tool_result'`(`plan.updated` 已在)。
2. `Chat.jsx` `handleStreamEvent` + `messages` 合并逻辑:
   - `agent.tool_call` → 生成一条 `kind:"tool_call"` 的时间线项(tool_name + 折叠的 arguments)。
   - `agent.tool_result` → `kind:"tool_result"` 项(可折叠 result;plan_tool 结果特殊高亮)。
   - `plan.updated` → `kind:"plan"` 项(显示 plan 标题 + 步骤勾选列表 + 文件路径)。
   - `session.message.appended` → 现有气泡逻辑不变。
   - 这些项一并进 `liveBuffer`,按 sequence_no 排序内联在对话流。
   - 历史渲染(`sessionPage.main_timeline` filter)同步放开这些 event_type。
3. `ChatPanel.jsx`:`messages.map` 按 `message.kind` 分支渲染:
   - 普通消息 → 现有左右气泡。
   - `tool_call`/`tool_result` → 居中的浅色"步骤卡片"(图标 + 工具名 + 可展开详情),非左右气泡。
   - `plan` → 步骤清单卡片(☑/☐ + 步骤文本)。
4. css:新增 `.timeline-step`、`.plan-card` 等轻量样式,区别于对话气泡。

### D. RuntimePanel plan 步骤数(顺带)
`Chat.jsx` 现在 `plan_steps:0` 写死。用最近一次 `plan.updated` 的 steps 数喂进 runtime,让右侧面板"Plan: N 个步骤"变真实。小改,顺手做。

---

## 测试与验证
1. **后端单测**:
   - `RuntimeAssembler` 注入假 SessionWorkspaceRepository,断言 `workspace_root` == 该 workspace 的 root_path;查不到时兜底 TEST_WORKSPACE_PATH。
   - 工具循环 emit:用假 executor 制造一轮 plan_tool 调用,断言落库的 domain events 含 `agent.tool_call`/`agent.tool_result`/`plan.updated`,payload 形状正确。
   - 复用现有 `test_plan_tool.py` 确保 plan 文件写入路径随 workspace_root 变化。
2. **回归**:`uv run pytest`(agent_service + gateway)全绿;e2e delegate 链路那条不受影响。
3. **前端**:`npm run lint` + `npm run build`。
4. **手测/冒烟**:发"帮我规划一下重构登录模块的步骤" → 观察 SSE 依次推 tool_call(plan_tool)→ tool_result → plan.updated → 最终回复;确认 `.AgentHub/session-workspaces/<uuid>/.AgentHub/plans/<run_id>.execution-plan.md` 真生成;前端时间线内联出现工具步骤卡片 + plan 清单。

## 提交(分层)
- commit 1: feat(agent_service) 按 workspace_id 解析 session workspace root,plan 落盘到正确目录
- commit 2: feat(agent_service) 工具循环 emit 每轮回复/工具调用/结果/plan 更新事件
- commit 3: feat(frontend) 时间线内联渲染工具调用/结果/plan 步骤 + RuntimePanel plan 步骤数

## 不做(范围外)
- token 级流式(已确认不要打字机)
- domain_events 索引迁移(事件量小)
- 工具调用的权限确认 UI(本期 agent 自动执行)
