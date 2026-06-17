# Session Streaming Incremental Chat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add true incremental assistant streaming, runtime SSE updates, and non-destructive frontend rendering for the session chat page.

**Architecture:** Keep `GET /sessions/{id}` as the durable snapshot source, but extend leader-session SSE with standardized incremental events emitted from the AgentScope runtime bridge. The frontend keeps a local live overlay for active streaming messages and runtime patches, using snapshot refetch only for initialization and recovery.

**Tech Stack:** FastAPI, AgentScope, Redis message bus, React 19, Vite, Vitest, Testing Library

---

## File Structure

- Modify: `backend/app/runtime/agentscope/chat_runtime.py`
  - Add structured session event publishing for assistant message lifecycle and runtime updates.
- Modify: `backend/app/api/session_stream.py`
  - Keep route shape stable; only adjust if event forwarding needs minor compatibility logic.
- Modify: `backend/tests/test_session_stream.py`
  - Add backend tests for incremental event emission and replay/live behavior.
- Modify: `frontend2/src/pages/Chat/Chat.jsx`
  - Replace refetch-on-every-event behavior with snapshot + live overlay state.
- Modify: `frontend2/src/utils/api.js`
  - Keep stream URL helper and session HTTP helpers stable; only extend if recovery helpers are needed.
- Modify: `frontend2/src/components/ChatPanel/ChatPanel.jsx`
  - Render an in-progress assistant bubble driven by stream events.
- Modify: `frontend2/src/components/RuntimePanel/RuntimePanel.jsx`
  - Consume incremental runtime/waiting state without full panel resets.
- Modify: `frontend2/src/pages/Chat/Chat.test.jsx`
  - Add frontend tests for incremental assistant updates and runtime updates.

### Task 1: Backend Stream Event Protocol

**Files:**
- Modify: `backend/tests/test_session_stream.py`
- Modify: `backend/app/runtime/agentscope/chat_runtime.py`

- [ ] **Step 1: Write the failing backend test for assistant message lifecycle events**

Add a test in `backend/tests/test_session_stream.py` that expects replay/live `session.event` payloads with `message.started`, `message.delta`, and `message.completed` for a leader session.

```python
def test_session_stream_emits_incremental_assistant_message_events() -> None:
    client = TestClient(create_app())
    created = _create_session(client, "Incremental Stream")

    client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "say hello"},
    )

    events = asyncio.run(
        _read_stream_response_events(client, created["session_id"], limit=4, timeout_secs=8.0),
    )

    event_types = [payload.get("type") for name, payload in events if name == "session.event"]
    assert "message.started" in event_types
    assert "message.delta" in event_types
    assert "message.completed" in event_types
```

- [ ] **Step 2: Run backend stream test to verify it fails**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_stream.py::test_session_stream_emits_incremental_assistant_message_events -v`

Expected: FAIL because the current stream does not emit standardized assistant incremental events.

- [ ] **Step 3: Add a helper to publish standardized assistant events**

In `backend/app/runtime/agentscope/chat_runtime.py`, add a helper that publishes a started event, one or more delta events, and a completed event for a fully materialized assistant message.

```python
    async def _publish_assistant_message_events(
        self,
        *,
        message_bus: RedisMessageBus,
        session_id: str,
        message_id: str,
        agent_name: str,
        text: str,
    ) -> None:
        await message_bus.session_publish_event(
            session_id,
            {
                "type": "message.started",
                "session_id": session_id,
                "message_id": message_id,
                "role": "assistant",
                "name": agent_name,
            },
        )
        if text:
            await message_bus.session_publish_event(
                session_id,
                {
                    "type": "message.delta",
                    "session_id": session_id,
                    "message_id": message_id,
                    "delta": text,
                },
            )
        await message_bus.session_publish_event(
            session_id,
            {
                "type": "message.completed",
                "session_id": session_id,
                "message_id": message_id,
            },
        )
```

- [ ] **Step 4: Hook assistant message event emission into the runtime bridge**

After `ChatService.run(...)` completes in `run_user_message(...)`, read the latest assistant message for the leader session and publish lifecycle events for any newly produced assistant reply.

```python
                before_messages = await storage.list_messages(user_id, session_id)
                before_ids = {message.id for message in before_messages}
                await chat_service.run(
                    user_id=user_id,
                    session_id=session_id,
                    agent_id=agent_id,
                    input_msg=UserMsg(name="user", content=content),
                )
                after_messages = await storage.list_messages(user_id, session_id)
                for message in after_messages:
                    if message.id in before_ids or getattr(message, "role", None) != "assistant":
                        continue
                    text = "\n".join(
                        block.text
                        for block in message.content
                        if getattr(block, "type", None) == "text"
                    )
                    await self._publish_assistant_message_events(
                        message_bus=message_bus,
                        session_id=session_id,
                        message_id=message.id,
                        agent_name=getattr(message, "name", agent_id),
                        text=text,
                    )
```

- [ ] **Step 5: Run backend stream test to verify it passes**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_stream.py::test_session_stream_emits_incremental_assistant_message_events -v`

Expected: PASS

### Task 2: Backend Runtime Update Events

**Files:**
- Modify: `backend/tests/test_session_stream.py`
- Modify: `backend/app/runtime/agentscope/chat_runtime.py`

- [ ] **Step 1: Write the failing backend test for runtime update events**

Add a test that expects `runtime.updated` or `waiting.updated` after a confirm-producing or callback-producing flow.

```python
def test_session_stream_emits_runtime_update_events() -> None:
    client = TestClient(create_app())
    created = _create_session(client, "Runtime Update Stream")

    events = asyncio.run(
        _read_stream_response_events(client, created["session_id"], limit=2, timeout_secs=8.0),
    )

    assert any(
        name == "session.event" and payload.get("type") in {"runtime.updated", "waiting.updated", "hint_block"}
        for name, payload in events
    )
```

- [ ] **Step 2: Run backend runtime event test to verify it fails**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_stream.py::test_session_stream_emits_runtime_update_events -v`

Expected: FAIL because no standardized runtime update event is emitted.

- [ ] **Step 3: Add a runtime update publish helper**

In `backend/app/runtime/agentscope/chat_runtime.py`, add a helper that emits runtime state patches.

```python
    async def _publish_runtime_updated(
        self,
        *,
        message_bus: RedisMessageBus,
        session_id: str,
        session_status: str,
        current_summary: str | None,
        waiting_items: list[dict],
        agent_statuses: list[dict],
    ) -> None:
        await message_bus.session_publish_event(
            session_id,
            {
                "type": "runtime.updated",
                "session_id": session_id,
                "session_status": session_status,
                "current_summary": current_summary,
                "waiting_items": waiting_items,
                "agent_statuses": agent_statuses,
            },
        )
```

- [ ] **Step 4: Publish runtime updates after user run, wakeup, and confirm continuation**

At the end of `run_user_message(...)`, `run_wakeup(...)`, and `continue_with_confirm_event(...)`, read the latest runtime/session projection and emit `runtime.updated`. If waiting changes but no other runtime fields change, also emit `waiting.updated`.

```python
                runtime_session = await storage.get_session(user_id, agent_id, session_id)
                waiting_items = []
                if runtime_session is not None:
                    waiting_items = [
                        {
                            "waiting_id": block.id,
                            "title": f"Confirm tool call: {block.name}",
                            "status": "pending",
                        }
                        for message in runtime_session.state.context
                        if hasattr(message, "get_content_blocks")
                        for block in message.get_content_blocks("tool_call")
                        if getattr(block, "state", None) == "asking"
                    ]
                await self._publish_runtime_updated(
                    message_bus=message_bus,
                    session_id=session_id,
                    session_status="running",
                    current_summary=None,
                    waiting_items=waiting_items,
                    agent_statuses=[],
                )
```

- [ ] **Step 5: Run backend runtime event test to verify it passes**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_stream.py::test_session_stream_emits_runtime_update_events -v`

Expected: PASS

### Task 3: Frontend Incremental Assistant Rendering

**Files:**
- Modify: `frontend2/src/pages/Chat/Chat.test.jsx`
- Modify: `frontend2/src/pages/Chat/Chat.jsx`
- Modify: `frontend2/src/components/ChatPanel/ChatPanel.jsx`

- [ ] **Step 1: Write the failing frontend test for assistant incremental bubble rendering**

Add a test in `frontend2/src/pages/Chat/Chat.test.jsx` that emits `message.started`, `message.delta`, and `message.completed`, then verifies a single assistant bubble grows in place.

```jsx
test('streams assistant reply into a single bubble', async () => {
  api.listSessions.mockResolvedValue({
    sessions: [{ session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' }],
  });
  api.listTeams.mockResolvedValue({ teams: [] });
  api.listWorkspaces.mockResolvedValue({ workspaces: [] });
  api.getSessionDetail.mockResolvedValue({
    session: { session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' },
    team: { name: 'Default Team' },
    messages: [],
    runtime: { current_summary: '', current_plan: null, waiting_items: [], agent_statuses: [] },
    workspace_status: { name: 'Project Alpha' },
  });

  render(<Chat />);
  await screen.findByRole('heading', { level: 3, name: 'Existing Session' });

  MockEventSource.instances[0].emit('session.event', { type: 'message.started', session_id: 'session-1', message_id: 'assistant-1', role: 'assistant', name: 'Leader Agent' });
  MockEventSource.instances[0].emit('session.event', { type: 'message.delta', session_id: 'session-1', message_id: 'assistant-1', delta: 'Hello' });
  MockEventSource.instances[0].emit('session.event', { type: 'message.delta', session_id: 'session-1', message_id: 'assistant-1', delta: ' world' });
  MockEventSource.instances[0].emit('session.event', { type: 'message.completed', session_id: 'session-1', message_id: 'assistant-1' });

  expect(screen.getByText('Hello world')).toBeTruthy();
});
```

- [ ] **Step 2: Run frontend incremental assistant test to verify it fails**

Run: `npm test -- src/pages/Chat/Chat.test.jsx`

Expected: FAIL because current SSE handling does not render assistant deltas directly.

- [ ] **Step 3: Add live assistant overlay state to Chat page**

In `frontend2/src/pages/Chat/Chat.jsx`, add local state for a streaming assistant message map keyed by `message_id`.

```jsx
  const [streamingMessages, setStreamingMessages] = useState({});

  function upsertStreamingMessage(messageId, patch) {
    setStreamingMessages((current) => ({
      ...current,
      [messageId]: {
        ...current[messageId],
        ...patch,
      },
    }));
  }
```

- [ ] **Step 4: Handle message lifecycle events directly from SSE**

Extend the EventSource handler to patch local chat state instead of refetching by default.

```jsx
    const handleSessionEvent = (rawEvent) => {
      const payload = JSON.parse(rawEvent.data);
      if (payload.type === 'message.started') {
        upsertStreamingMessage(payload.message_id, {
          message_id: payload.message_id,
          kind: 'message',
          role: 'agent',
          author: payload.name || 'Leader Agent',
          content: '',
          streaming: true,
        });
        return;
      }
      if (payload.type === 'message.delta') {
        setStreamingMessages((current) => ({
          ...current,
          [payload.message_id]: {
            ...current[payload.message_id],
            content: `${current[payload.message_id]?.content || ''}${payload.delta || ''}`,
            streaming: true,
          },
        }));
        return;
      }
      if (payload.type === 'message.completed') {
        upsertStreamingMessage(payload.message_id, { streaming: false, completed: true });
        return;
      }
      void reloadDetail();
      void reloadSessions();
    };
```

- [ ] **Step 5: Merge persisted and live messages for rendering**

In `frontend2/src/pages/Chat/Chat.jsx`, combine snapshot messages, optimistic user messages, and streaming assistant overlays without clearing the existing timeline.

```jsx
  const messages = useMemo(() => {
    const baseMessages = (detail?.messages ?? []).map((message) => ({
      message_id: message.id,
      kind: 'message',
      role: message.role === 'user' ? 'user' : 'agent',
      author: message.role === 'user' ? '你' : message.name || 'Leader Agent',
      content: renderContentBlocks(message.content),
    }));
    const persistedIds = new Set(baseMessages.map((message) => message.message_id));
    const liveAssistant = Object.values(streamingMessages).filter(
      (message) => !persistedIds.has(message.message_id),
    );
    return [...baseMessages, ...optimisticMessages.filter((m) => m.session_id === activeSessionId), ...liveAssistant];
  }, [activeSessionId, detail, optimisticMessages, streamingMessages]);
```

- [ ] **Step 6: Render streaming assistant state in the chat panel**

In `frontend2/src/components/ChatPanel/ChatPanel.jsx`, keep the message bubble visible and add a small streaming decoration instead of replacing the panel.

```jsx
        <div className="message-bubble">
          {item.content}
          {item.streaming ? <span className="message-stream-cursor">|</span> : null}
        </div>
```

- [ ] **Step 7: Run frontend incremental assistant test to verify it passes**

Run: `npm test -- src/pages/Chat/Chat.test.jsx`

Expected: PASS

### Task 4: Frontend Runtime Incremental Updates

**Files:**
- Modify: `frontend2/src/pages/Chat/Chat.test.jsx`
- Modify: `frontend2/src/pages/Chat/Chat.jsx`
- Modify: `frontend2/src/components/RuntimePanel/RuntimePanel.jsx`

- [ ] **Step 1: Write the failing frontend test for runtime event patching**

Add a test that emits `runtime.updated` and verifies the right panel changes without waiting for a full detail refetch.

```jsx
test('updates runtime panel from incremental runtime events', async () => {
  api.listSessions.mockResolvedValue({
    sessions: [{ session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' }],
  });
  api.listTeams.mockResolvedValue({ teams: [] });
  api.listWorkspaces.mockResolvedValue({ workspaces: [] });
  api.getSessionDetail.mockResolvedValue({
    session: { session_id: 'session-1', name: 'Existing Session', status: 'idle', updated_at: '2026-06-17T18:00:00' },
    team: { name: 'Default Team' },
    messages: [],
    runtime: { current_summary: '', current_plan: null, waiting_items: [], agent_statuses: [] },
    workspace_status: { name: 'Project Alpha' },
  });

  render(<Chat />);
  await screen.findByText('状态：idle');

  MockEventSource.instances[0].emit('session.event', {
    type: 'runtime.updated',
    session_id: 'session-1',
    session_status: 'running',
    current_summary: 'agent is working',
    waiting_items: [],
    agent_statuses: [],
  });

  expect(screen.getByText('状态：running')).toBeTruthy();
  expect(screen.getByText('agent is working')).toBeTruthy();
});
```

- [ ] **Step 2: Run frontend runtime event test to verify it fails**

Run: `npm test -- src/pages/Chat/Chat.test.jsx`

Expected: FAIL because runtime panel currently depends on snapshot refresh for state changes.

- [ ] **Step 3: Add runtime overlay state in Chat page**

In `frontend2/src/pages/Chat/Chat.jsx`, add a local runtime patch state for the active session.

```jsx
  const [runtimePatch, setRuntimePatch] = useState(null);
```

- [ ] **Step 4: Patch runtime state on `runtime.updated` and `waiting.updated`**

Extend the SSE handler to update the runtime patch locally.

```jsx
      if (payload.type === 'runtime.updated') {
        setRuntimePatch({
          session_status: payload.session_status,
          current_summary: payload.current_summary,
          waiting_items: payload.waiting_items,
          agent_statuses: payload.agent_statuses,
        });
        return;
      }
      if (payload.type === 'waiting.updated') {
        setRuntimePatch((current) => ({
          ...current,
          waiting_items: payload.waiting_items,
        }));
        return;
      }
```

- [ ] **Step 5: Merge runtime snapshot and runtime overlay for rendering**

In `frontend2/src/pages/Chat/Chat.jsx`, compute the runtime prop from snapshot + patch instead of detail only.

```jsx
  const runtime = detail
    ? {
        session_title: detail.session.name,
        session_status: runtimePatch?.session_status ?? detail.session.status,
        session_team: detail.team?.name ?? '—',
        session_workspace: detail.workspace_status?.name ?? '—',
        agent_status: runtimePatch?.session_status ?? detail.session.status,
        task_status: runtimePatch?.session_status ?? detail.session.status,
        plan_steps: detail.runtime?.current_plan?.steps?.length ?? 0,
        current_summary: runtimePatch?.current_summary ?? detail.runtime?.current_summary ?? '暂无 summary',
        waiting_items: runtimePatch?.waiting_items ?? detail.runtime?.waiting_items ?? [],
        agent_statuses: runtimePatch?.agent_statuses ?? detail.runtime?.agent_statuses ?? [],
      }
    : null;
```

- [ ] **Step 6: Run frontend runtime event test to verify it passes**

Run: `npm test -- src/pages/Chat/Chat.test.jsx`

Expected: PASS

### Task 5: Recovery, Verification, and Docs Sync

**Files:**
- Modify: `frontend2/src/pages/Chat/Chat.jsx`
- Modify: `docs/superpowers/specs/2026-06-17-session-streaming-incremental-chat-design.md` (only if implementation reveals clarified behavior)

- [ ] **Step 1: Add conservative recovery fallback for unknown event types**

Keep full detail reload only for reconnect, malformed payloads, or unknown event types.

```jsx
      try {
        const payload = JSON.parse(rawEvent.data);
        if (!payload?.type) {
          void reloadDetail();
          void reloadSessions();
          return;
        }
        // known event handlers...
      } catch {
        void reloadDetail();
        void reloadSessions();
      }
```

- [ ] **Step 2: Run the focused frontend and backend tests**

Run: `& ".\.venv\Scripts\python.exe" -m pytest backend/tests/test_session_stream.py -v`

Expected: PASS

Run: `npm test -- src/pages/Workspace/Workspace.test.jsx src/pages/Chat/Chat.test.jsx`

Expected: PASS

- [ ] **Step 3: Run final repo-facing verification for touched surfaces**

Run: `npm run lint`

Expected: PASS

Run: `npm run build`

Expected: PASS

- [ ] **Step 4: Sync spec wording if implementation discovered a smaller stable chunk boundary**

If AgentScope only exposes paragraph/block-level chunks rather than token deltas, update:

```markdown
- `message.delta` represents the smallest stable assistant text chunk exposed by the
  current AgentScope runtime bridge, not necessarily provider token-level output.
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/runtime/agentscope/chat_runtime.py backend/tests/test_session_stream.py frontend2/src/pages/Chat/Chat.jsx frontend2/src/components/ChatPanel/ChatPanel.jsx frontend2/src/components/RuntimePanel/RuntimePanel.jsx frontend2/src/pages/Chat/Chat.test.jsx docs/superpowers/specs/2026-06-17-session-streaming-incremental-chat-design.md docs/superpowers/plans/2026-06-17-session-streaming-incremental-chat-implementation.md
git commit -m "feat: add incremental session streaming"
```
