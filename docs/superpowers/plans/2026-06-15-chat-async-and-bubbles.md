# 对话实现：异步 LLM + 即时回显 + 左右气泡布局

## 问题拆解

### A. POST /messages 500（真 bug，必须修）
`SessionMessageService.send()` → `AgentRunInputService.input()` **同步**跑完整个 LLM
orchestrator 工具循环（`_run_internal_orchestrator_tool_loop`，最多 8 轮 LLM 调用）才返回。
耗时远超 gateway httpx 的 10s 超时 → gateway 抛 `ReadTimeout` 返回 500，而 agent_service
自己最终仍跑完返回 200（日志可见）。

**不能靠调大超时**：那会让 POST 阻塞整个 LLM 时长，SSE 就失去意义。
正确做法：录入用户消息后**异步**跑 LLM，POST 立即返回，回复经 SSE 回流。

### B. 对话 UI 需求
1. 用户发送后**立即**看到自己那句话（乐观回显，不等 SSE 往返）。
2. 用户在右、agent 在左，头像不同（参考 EchoMind 风格，但布局按用户要求左右分置）。
3. SSE 已有且可用（自适应轮询 events），异步化后才能真正发挥作用。

## 方案

### 后端：异步执行 LLM（agent_service）
沿用 `DelegateTool._run_async` 的 daemon 线程模式。

`agent_service/app/services/session_message_service.py`：
- `send()` 拆成两段：
  1. **同步**：解析 session（不存在→ ValueError→404）、`_resolve_run_id`（可能建 run）、
     构造 `AgentRunInputRequest`。这些快，保留同步以便正确返回错误。
  2. **异步**：用 daemon 线程跑 `self._resolve_input_service().input(run_id, payload)`。
- `send()` 立即返回 `AgentRunInputResponse(run_id=run_id, status="accepted")`。
- 注入点：构造函数加 `async_runner=None`，默认 `lambda job: threading.Thread(target=job, daemon=True).start()`；
  测试可传同步 runner 保持现有单测行为。

线程安全：domain_events 走 SQLite，每次调用 `get_connection()` 开/关连接（同线程内创建关闭，
不跨线程共享 connection），后台线程写事件、SSE 轮询读事件互不干扰。

注意：用户消息的 `session.message.appended` 事件在 `input()` 内部、LLM 调用**之前**持久化
（`_persist_domain_event`），所以异步后 SSE 仍能在 ~0.3s 内先推出用户消息、再推 agent 回复。

gateway 侧无需改超时（POST 现在快速返回）。

### 前端：乐观回显 + 左右布局 + 滚动
`frontend/src/pages/Chat/Chat.jsx`：
- `handleSendMessage(content)`：发请求前先把用户消息推入 `liveBuffer`（乐观），用临时
  `pending` 标记 + 负数/临时 sequence_no 占位。SSE 回流真实用户事件后，按 content+role 去重
  覆盖乐观项（或：乐观项用 `optimistic: true`，合并时若已有真实 user 事件则丢弃乐观项）。
  - 去重策略：真实事件有正整数 `sequence_no`；乐观项标 `optimistic`。`messages` 合并时，
    若存在与乐观项 content 相同的真实 user 消息，则跳过该乐观项。
- 发送态：`postMessage` 的 `isLoading` 暂时为 true，期间禁用发送按钮。

`frontend/src/components/ChatPanel/ChatPanel.jsx`：
- 加 `messageEndRef` + `useEffect` 滚动到底（参考 EchoMind）。
- 消息渲染：`role === 'user'` → wrapper 加 `send`，否则 `receive`。
- 头像：user 显示「你」首字 + `self` 类（绿色）；agent 显示名字首字（主题色）。
- 可选：`pending` 项显示 `stream-cursor`（本轮先不做流式分片，仅乐观态可加轻提示）。

`frontend/src/components/ChatPanel/ChatPanel.css`：
- 新增 `.message-wrapper.send { flex-direction: row-reverse; }` 让用户消息整体靠右
  （头像在右、气泡在右）。
- `.message-wrapper.send .message-content { align-items: flex-end; }`
- user 气泡保留现有 `.send` 配色；agent 用 `.receive` 白底。
- 保留现有 `.message-avatar.self` 绿色区分头像。

## 不做（本轮范围外）
- 真正的 token 级流式（SSE 当前是整段 `session.message.appended`，非增量分片）。
- 多 agent 子任务在主时间线的渲染、plan 面板联动。

## 验证
1. 后端：`uv run pytest`（确认 session_message / agent_run_input 相关单测仍绿；
   若单测依赖同步返回结果，用注入的同步 async_runner）。
2. 手测端到端：
   - 发一句话 → 立即出现在右侧（乐观）。
   - POST 快速返回 200（不再 500/超时）。
   - 数秒后 agent 回复经 SSE 出现在左侧。
   - 刷新页面后历史顺序正确、无重复（乐观项已被真实事件取代）。
3. `npm run lint` + `npm run build` 绿。

## 提交
后端异步修复 1 个 commit，前端 UI 1 个 commit。
