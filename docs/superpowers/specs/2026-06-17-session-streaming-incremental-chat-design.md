# Session Streaming Incremental Chat Design

## Context

`frontend2/` already supports:

- session creation
- workspace creation
- sending messages
- session detail rendering
- runtime actions for waiting resolve and cancel
- session SSE subscription

However, the current streaming behavior is still snapshot-oriented rather than truly
incremental:

- the backend `GET /api/v1/sessions/{session_id}/stream` endpoint emits `session.ready`
  plus generic `session.event` envelopes
- the frontend treats every stream event as a signal to refetch session detail
- assistant replies only appear after the backend has persisted them into the session
  snapshot and the frontend has reloaded that snapshot

This causes a mismatch with the intended AgentScope-native interaction model:

- the chat timeline should preserve existing messages while background updates arrive
- the user message should appear immediately
- the assistant message should appear as an incremental streaming bubble
- the runtime panel should update from SSE-driven runtime events rather than from full
  snapshot replacement

## Goal

Add a true incremental streaming protocol between the backend AgentScope runtime and
`frontend2/` so that:

1. entering a session loads the current snapshot once and then stays live via SSE
2. user messages appear immediately in the timeline
3. assistant replies stream into a single in-progress bubble
4. runtime state changes update the right panel incrementally
5. snapshot refetch is reserved for initialization, reconnection, and recovery only

## Non-Goals

- token-perfect reproduction of provider-native partial tokens if AgentScope only exposes
  chunked text blocks at a higher level
- redesigning the full backend session persistence model
- changing workspace/team/session product semantics
- replacing SSE with WebSocket
- rebuilding the frontend around Redux or RTK Query

## Current Behavior and Root Cause

### Backend Today

`backend/app/api/session_stream.py` simply forwards replayed and live Redis message bus
entries as SSE `session.event` packets.

The only clearly structured business event currently published onto the leader session
stream in this repository is the hint callback path:

- `hint_block`

AgentScope already publishes reply-stream events to the session message bus during
`ChatService.run(...)`. The missing piece is not raw streaming transport, but that the
current frontend does not yet consume the native AgentScope event model incrementally.

The first implementation priority should therefore be:

- consume AgentScope-native `REPLY_START` / `TEXT_BLOCK_DELTA` / `REPLY_END`
- consume `REQUIRE_USER_CONFIRM` / `REQUIRE_EXTERNAL_EXECUTION` for waiting state
- keep `HINT_BLOCK` for callback/hint visibility

Only if those native events prove insufficient in a specific runtime path should the
backend add an additional compatibility mapping layer.

### Frontend Today

`frontend2/src/pages/Chat/Chat.jsx` uses SSE as a refresh trigger. When an event arrives,
the frontend reloads session list and session detail. This is good enough for stable
eventual consistency, but it is not enough for incremental rendering.

## Chosen Approach

Use a **hybrid snapshot + incremental event** protocol based primarily on the native
AgentScope event stream.

### Why this approach

- it preserves the current durable snapshot model as the source of truth
- it reuses the incremental events AgentScope already emits for the active live session
- it keeps reconnect and recovery logic simple
- it avoids forcing the frontend to infer assistant stream state from opaque generic
  events

### High-Level Flow

1. Frontend enters session page
2. Frontend loads `GET /api/v1/sessions/{session_id}` once
3. Frontend opens `GET /api/v1/sessions/{session_id}/stream`
4. Backend emits incremental session events during runtime execution
5. Frontend updates the local session timeline and runtime panel directly from events
6. Frontend only refetches full snapshot when:
   - the stream reconnects
   - an event sequence is missing or invalid
   - the user manually refreshes

## Backend Event Protocol

### First Implementation Principle

The first implementation should consume **AgentScope native event payloads directly**
rather than immediately inventing a parallel custom event protocol.

That means the frontend should first understand and render these native event types:

- `REPLY_START`
- `TEXT_BLOCK_START`
- `TEXT_BLOCK_DELTA`
- `TEXT_BLOCK_END`
- `REPLY_END`
- `REQUIRE_USER_CONFIRM`
- `REQUIRE_EXTERNAL_EXECUTION`
- `HINT_BLOCK`

If, after integrating these, a specific runtime path still lacks enough information for
stable UI rendering, then a smaller backend compatibility layer may be added. That layer
must be justified by a concrete missing native event, not by preference alone.

第一版保持外层 SSE 事件名不变，避免破坏当前接口兼容性：

- `session.ready`
- `session.event`

真正的业务语义放在 `session.event` 的 payload 内部，通过 `type` 区分。

### 第一版优先消费的原生事件

第一版前端应优先消费以下 AgentScope 原生事件：

- `REPLY_START`
- `TEXT_BLOCK_DELTA`
- `REPLY_END`
- `REQUIRE_USER_CONFIRM`
- `REQUIRE_EXTERNAL_EXECUTION`
- `HINT_BLOCK`

其中：

- `REPLY_START / TEXT_BLOCK_DELTA / REPLY_END` 负责主聊天区 assistant 流式输出
- `REQUIRE_USER_CONFIRM / REQUIRE_EXTERNAL_EXECUTION` 负责 waiting 区域增量变化
- `HINT_BLOCK` 负责 callback / wakeup hint 的可见性

第一版可以不强依赖自定义的 `message.started/message.delta/message.completed`
协议名。只有在需要兼容不同前端消费层或者补齐 AgentScope 原生信息不足时，才考虑额外
加映射层。

### 第一版事件边界

第一版需要明确区分三类信息：

1. **聊天主区的流式消息事件**
2. **右侧运行态的增量更新事件**
3. **已有 callback / hint 事件**

第一版**不要求**把工具调用过程、子 agent 全过程文本流都直接灌进聊天主区。

第一版的边界定义如下：

- `message.*`：只负责主聊天区里的 leader assistant 流式回复
- `runtime.updated` / `waiting.updated`：负责右侧 runtime panel 的状态变化
- `hint_block`：保留现有 worker callback / wakeup hint 可见性语义
- 工具调用、子 agent 调用：
  - 先通过 runtime 状态体现
  - 需要进入主聊天区的结果，第一版先通过 `hint_block` 体现
  - 暂不单独设计完整的 `tool.started/tool.completed` 或 `subagent.delta` 协议

这样可以先解决“真正流式聊天输出”和“右侧运行态实时变化”两个核心问题，
避免第一版把事件协议做得过宽、过散。

### 1. `message.started`

含义：assistant 开始输出一条新的消息。

```json
{
  "type": "message.started",
  "session_id": "...",
  "message_id": "...",
  "role": "assistant",
  "name": "Leader Agent"
}
```

前端收到后应当：

- 在聊天主区创建一个新的 assistant 气泡
- 将这条气泡标记为“正在输出”

这个事件表示“有一条 assistant 消息开始生成”，不是“整轮任务开始”。

### 2. `message.delta`

含义：当前 assistant 消息追加了一段新的文本内容。

```json
{
  "type": "message.delta",
  "session_id": "...",
  "message_id": "...",
  "delta": "next text chunk"
}
```

前端收到后应当：

- 找到这条 `message_id` 对应的 assistant 气泡
- 将 `delta` 追加到已显示文本后面

这是真正流式渲染的关键事件。

### 3. `message.completed`

含义：当前 assistant 消息输出完成。

```json
{
  "type": "message.completed",
  "session_id": "...",
  "message_id": "..."
}
```

前端收到后应当：

- 将该 assistant 气泡从“流式中”切换到“完成态”
- 结束光标闪动或 typing 装饰

### 4. `runtime.updated`

含义：右侧运行态整体发生变化。

```json
{
  "type": "runtime.updated",
  "session_id": "...",
  "session_status": "running",
  "current_summary": "...",
  "waiting_items": [...],
  "agent_statuses": [...]
}
```

它主要服务于右侧 runtime panel，可覆盖这些变化：

- session status 变化
- summary 变化
- agent_statuses 变化
- worker / subagent 执行状态变化
- plan 或等待态的整体状态变化

前端收到后应当局部更新 runtime panel，而不是重新清空整页后回拉完整 detail。

### 5. `waiting.updated`

含义：waiting items 发生变化。

```json
{
  "type": "waiting.updated",
  "session_id": "...",
  "waiting_items": [...]
}
```

它主要用于右侧 waiting 区域的精确增量更新，例如：

- 新增 confirm waiting
- resolve / reject 后 waiting 消失
- external_result 类型 waiting 出现或更新

### 6. 保留现有 `hint_block`

继续保留当前 callback / hint 事件：

```json
{
  "type": "hint_block",
  "reply_id": "...",
  "block_id": "...",
  "source": "...",
  "hint": "..."
}
```

它的含义不是“普通 assistant 文本流”，而是：

- worker callback
- 子 agent 回调提示
- wakeup hint

第一版里，`hint_block` 继续承担“需要进入主会话可见域的 callback/hint 信息”职责。

### 工具调用与子 Agent 调用是否包含在协议里

第一版答案是：**包含其结果与状态，但不完整展开全过程文本流。**

#### 工具调用

第一版不额外定义：

- `tool.started`
- `tool.completed`
- `tool.failed`

工具调用带来的可见变化先通过以下两条路径体现：

- 影响右侧状态的，进入 `runtime.updated` / `waiting.updated`
- 需要进入主聊天区的 callback/hint 结果，进入 `hint_block`

#### 子 Agent 调用

第一版不把每个子 agent 的中间文本流直接渲染到主聊天区。

第一版只要求：

- 子 agent 的运行状态进入 `runtime.updated` 里的 `agent_statuses`
- 子 agent 的 callback / hint 结果进入 `hint_block`

这样可以避免主聊天区在第一版就被大量工具过程、worker 中间态刷乱。

后续如果需要更细的过程可视化，再补专门事件协议，例如：

- `tool.started`
- `tool.completed`
- `subagent.started`
- `subagent.completed`
- `subagent.delta`

但这些都不属于第一版流式输出优化的必需范围。

## Backend Integration Strategy

### Event Production Boundary

The correct integration point is the AgentScope runtime bridge layer rather than the API
route layer.

Target area:

- `backend/app/runtime/agentscope/chat_runtime.py`

This layer already owns:

- `run_user_message(...)`
- `run_wakeup(...)`
- confirm continuation
- hint persistence + hint event publish

The design expectation is:

1. intercept assistant output progression while `ChatService.run(...)` is executing
2. translate assistant output into the standardized `message.started` /
   `message.delta` / `message.completed` events
3. publish runtime status changes into `runtime.updated` and `waiting.updated`

### Required Investigation Constraint

Implementation must first verify how AgentScope currently exposes streaming reply output
inside the runtime path. The repository already demonstrates durable storage integration,
but not incremental assistant event emission. The implementation must inspect AgentScope's
chat runtime hooks and reuse them rather than inventing a parallel synthetic message loop.

## Frontend State Model

### Snapshot State

The frontend still keeps one durable snapshot from `GET detail` containing:

- persisted messages
- session metadata
- runtime data
- workspace/team info

This snapshot remains the recovery and initialization base.

### Live Overlay State

On top of the snapshot, the frontend keeps a live overlay for the active session:

- optimistic user messages
- in-progress assistant streaming bubble
- runtime patch state from SSE

The rendered session view becomes:

- `rendered_messages = persisted_messages + optimistic_messages + streaming_assistant_overlay`
- `rendered_runtime = snapshot_runtime patched by latest runtime events`

### Frontend Event Handling

#### Enter Session

1. load snapshot via `GET /sessions/{id}`
2. render immediately
3. open `EventSource`
4. on `session.ready`, keep current UI and do not clear the timeline

#### Send User Message

1. append optimistic user message immediately
2. `POST /sessions/{id}/messages`
3. keep optimistic message visible until a matching persisted user message arrives or a
   recovery snapshot replaces it

#### Assistant Streaming

1. on `message.started`, create empty assistant bubble
2. on `message.delta`, append text to the active assistant bubble
3. on `message.completed`, mark that bubble as done

#### Runtime Updates

1. on `runtime.updated`, patch runtime panel state
2. on `waiting.updated`, patch waiting area state
3. on `hint_block`, append or surface hint block without clearing the timeline

#### Recovery

Full `GET detail` refetch should only happen when:

- stream reconnects after disconnect
- event payload is malformed or unknown
- stream ordering appears broken
- user triggers manual refresh

## Frontend UI Behavior

### Chat Timeline

- existing history remains visible during stream activity
- user message appears immediately on send
- assistant bubble appears before the response is complete
- assistant text grows incrementally inside the same bubble
- no full-panel loading fallback after initialization unless there is no snapshot at all

### Runtime Panel

- session status changes without page flicker
- waiting items appear/disappear from runtime events
- cancel and waiting actions still use existing HTTP endpoints
- action results are confirmed by incremental runtime updates or recovery snapshot

## Compatibility and Migration

The transition should be incremental:

1. backend begins publishing the new structured `session.event` payloads
2. frontend consumes them if present
3. existing snapshot fallback remains available during rollout

This allows the system to keep working if some runtime paths still only produce persisted
snapshot results during the migration.

## Verification

The work is complete when all of the following are true:

1. entering a session loads history once and does not clear it on subsequent stream events
2. sending a message shows the user bubble immediately
3. assistant replies appear incrementally in a single streaming bubble
4. runtime panel status updates without full-page flicker
5. waiting resolve and cancel still work correctly
6. reconnect/recovery can restore consistency from `GET detail`
7. backend and frontend tests cover the new event protocol and UI behavior

## Risks and Controls

### Risk: AgentScope does not expose a convenient assistant delta hook

Control:

- inspect runtime hooks before implementation
- if only higher-level assistant block updates are available, stream at the smallest
  stable chunk boundary AgentScope provides rather than inventing token semantics

### Risk: snapshot and overlay diverge

Control:

- snapshot remains the recovery source of truth
- clear overlay entries when the corresponding persisted message is observed
- force recovery refetch on invalid event sequences

### Risk: too many full refreshes remain in the code path

Control:

- reserve full detail reload for initialization and recovery only
- keep normal stream-driven rendering incremental by default
