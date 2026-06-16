# Backend Runtime Mainline Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backend runtime mainline truly asynchronous and verifiable by fixing immediate-return message execution, cancel interruption, robust waiting projection, and higher-fidelity session stream tests.

**Architecture:** Keep the current product-layer `Session` contract and AgentScope runtime bridge, but move `send_message` to real fire-and-forget execution through `ChatRunRegistry`, centralize runtime-to-product state synchronization in `RuntimeService`, and verify state/event behavior with deterministic service, API, and SSE tests. Do not introduce new persistence layers or worker orchestration; strengthen the existing Redis-backed runtime path with minimal structural change.

**Tech Stack:** FastAPI, AgentScope 2.0.1, Redis, asyncio, pytest, Ruff.

---

## File Structure

- Modify: `backend/app/services/runtime_service.py`
  Make `send_message(...)` return immediately after spawning a background task, centralize runtime sync/finalization, strengthen cancel handling, and upgrade waiting extraction/merge logic.
- Modify: `backend/app/api/sessions.py`
  Keep `202` semantics aligned with actual immediate-return runtime behavior.
- Modify: `backend/app/api/session_stream.py`
  Keep current SSE structure, with any minimal stability adjustments needed for reliable replay/live testing.
- Create: `backend/tests/test_session_stream.py`
  Isolate SSE-specific tests for ready/replay/live/cancel visibility.
- Modify: `backend/tests/test_runtime_service.py`
  Add failing service-level tests for immediate return, cancel interruption, full-context waiting extraction, and local waiting status preservation.
- Modify: `backend/tests/test_session_api.py`
  Keep API mainline tests focused on message acceptance, async writeback, and cancel state behavior.

## Task 1: Harden RuntimeService Async Execution And Waiting Projection

**Files:**
- Modify: `backend/app/services/runtime_service.py`
- Modify: `backend/tests/test_runtime_service.py`
- Test: `backend/tests/test_runtime_service.py`

- [ ] **Step 1: Write the failing immediate-return and waiting-projection tests**

```python
import asyncio
import threading
import time
from types import SimpleNamespace

from agentscope.message import AssistantMsg, ToolCallBlock, UserMsg

from app.domain.sessions.models import ProductSessionRecord, WaitingItem
from app.services.runtime_service import RuntimeService


class StubSessionRepository:
    def __init__(self, record: ProductSessionRecord) -> None:
        self.record = record

    async def get(self, session_id: str) -> ProductSessionRecord | None:
        return self.record if self.record.session_id == session_id else None

    async def upsert(self, record: ProductSessionRecord) -> ProductSessionRecord:
        self.record = record
        return record


class InlineChatRunRegistry:
    def __init__(self) -> None:
        self.tasks: dict[str, asyncio.Task] = {}

    def spawn(self, coroutine, session_id: str) -> asyncio.Task:
        task = asyncio.create_task(coroutine)
        self.tasks[session_id] = task
        return task

    def get(self, session_id: str) -> asyncio.Task | None:
        return self.tasks.get(session_id)


def test_runtime_service_send_message_returns_before_slow_runtime_finishes() -> None:
    finished = threading.Event()

    class SlowChatRuntime:
        async def run_user_message(self, **kwargs) -> None:
            await asyncio.sleep(0.2)
            finished.set()

    record = ProductSessionRecord(
        session_id="session-1",
        name="Demo",
        team_id="team-1",
        leader_agent_id="leader-agent",
        workspace_id="workspace-1",
    )
    repository = StubSessionRepository(record)
    registry = InlineChatRunRegistry()
    service = RuntimeService(
        session_repository=repository,
        chat_runtime=SlowChatRuntime(),
        chat_run_registry=registry,
    )

    async def scenario() -> float:
        started = time.perf_counter()
        await service.send_message("session-1", "hello")
        elapsed = time.perf_counter() - started
        await registry.get("session-1")
        return elapsed

    elapsed = asyncio.run(scenario())

    assert elapsed < 0.1
    assert finished.is_set()
    assert repository.record.status == "running"


def test_runtime_service_extract_waiting_items_scans_full_context_and_deduplicates() -> None:
    first = AssistantMsg(
        name="leader",
        content=[
            ToolCallBlock(
                id="wait-1",
                name="Write",
                input='{"path":"foo.py"}',
                state="asking",
            )
        ],
    )
    second = AssistantMsg(
        name="leader",
        content=[
            ToolCallBlock(
                id="wait-1",
                name="Write",
                input='{"path":"foo.py"}',
                state="submitted",
            ),
            ToolCallBlock(
                id="wait-2",
                name="Deploy",
                input='{"env":"prod"}',
                state="asking",
            ),
        ],
    )
    runtime_session = SimpleNamespace(
        state=SimpleNamespace(context=[UserMsg(name="user", content="go"), first, second]),
    )

    waiting_items = RuntimeService._extract_waiting_items(
        runtime_session,
        source_runtime_id="leader-agent",
    )

    assert [item.waiting_id for item in waiting_items] == ["wait-1", "wait-2"]
    assert waiting_items[0].waiting_kind == "external_result"
    assert waiting_items[1].waiting_kind == "confirm"


def test_runtime_service_merge_waiting_items_preserves_resolved_status() -> None:
    existing = [
        WaitingItem(
            waiting_id="wait-1",
            source_type="leader",
            source_runtime_id="leader-agent",
            waiting_kind="confirm",
            title="Confirm tool call: Write",
            message="Tool Write requires confirmation.",
            payload={"tool_name": "Write", "tool_input": '{"path":"foo.py"}'},
            status="resolved",
        )
    ]
    extracted = [
        WaitingItem(
            waiting_id="wait-1",
            source_type="leader",
            source_runtime_id="leader-agent",
            waiting_kind="confirm",
            title="Confirm tool call: Write",
            message="Tool Write requires confirmation.",
            payload={"tool_name": "Write", "tool_input": '{"path":"foo.py"}'},
            status="pending",
        ),
        WaitingItem(
            waiting_id="wait-2",
            source_type="leader",
            source_runtime_id="leader-agent",
            waiting_kind="external_result",
            title="Await external result: Deploy",
            message="Tool Deploy is waiting for external execution result.",
            payload={"tool_name": "Deploy", "tool_input": '{"env":"prod"}'},
            status="pending",
        ),
    ]

    merged = RuntimeService._merge_waiting_items(existing, extracted)

    assert merged[0].waiting_id == "wait-1"
    assert merged[0].status == "resolved"
    assert merged[1].waiting_id == "wait-2"
    assert merged[1].status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_runtime_service.py -v`
Expected: FAIL because `send_message(...)` still waits for the spawned task, `_extract_waiting_items(...)` only scans the last message, and `_merge_waiting_items(...)` does not exist yet.

- [ ] **Step 3: Write the minimal RuntimeService implementation changes**

```python
# backend/app/services/runtime_service.py
from __future__ import annotations

import asyncio
import contextlib

from agentscope.message import AssistantMsg

from app.domain.sessions.models import WaitingItem
from app.infrastructure.storage.session_repository import SessionRepository
from app.runtime.agentscope.chat_runtime import AgentScopeChatRuntime
from app.runtime.agentscope.confirm_runtime import ConfirmRuntime
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime


class RuntimeService:
    def __init__(
        self,
        session_repository: SessionRepository,
        chat_runtime: AgentScopeChatRuntime | None = None,
        state_runtime: AgentScopeSessionStateRuntime | None = None,
        confirm_runtime: ConfirmRuntime | None = None,
        chat_run_registry=None,
    ) -> None:
        self._session_repository = session_repository
        self._chat_runtime = chat_runtime
        self._state_runtime = state_runtime
        self._confirm_runtime = confirm_runtime
        self._chat_run_registry = chat_run_registry

    async def send_message(self, session_id: str, content: str) -> None:
        session = await self._session_repository.get(session_id)
        if session is None:
            raise KeyError(session_id)
        if session.status not in {"idle", "failed"}:
            raise ValueError("Session is not ready for a new message")

        session.status = "running"
        await self._session_repository.upsert(session)

        if self._chat_runtime is None or self._chat_run_registry is None:
            return

        async def _run_and_sync() -> None:
            run_failed = False
            try:
                await self._chat_runtime.run_user_message(
                    user_id="default-user",
                    session_id=session.session_id,
                    agent_id=session.leader_agent_id,
                    content=content,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                run_failed = True
                raise
            finally:
                await self._sync_runtime_state(
                    session_id=session.session_id,
                    agent_id=session.leader_agent_id,
                    failed=run_failed,
                )

        self._chat_run_registry.spawn(_run_and_sync(), session_id=session.session_id)

    async def cancel(self, session_id: str) -> None:
        session = await self._session_repository.get(session_id)
        if session is None:
            raise KeyError(session_id)

        session.status = "cancelling"
        await self._session_repository.upsert(session)

        if self._chat_run_registry is not None:
            task = self._chat_run_registry.get(session_id)
            if task is not None and not task.done():
                task.cancel()

        if self._chat_runtime is not None:
            await self._chat_runtime.publish_cancel(session_id)

    async def _sync_runtime_state(self, session_id: str, agent_id: str, failed: bool) -> None:
        latest = await self._session_repository.get(session_id)
        if latest is None:
            return
        if self._state_runtime is None:
            if latest.status == "cancelling":
                latest.status = "idle"
            elif failed:
                latest.status = "failed"
            await self._session_repository.upsert(latest)
            return

        runtime_session = await self._state_runtime.get_runtime_session(
            user_id="default-user",
            session_id=session_id,
            agent_id=agent_id,
        )
        if runtime_session is not None:
            latest.current_summary_snapshot = runtime_session.state.summary
            extracted = self._extract_waiting_items(runtime_session, source_runtime_id=agent_id)
            latest.waiting_items = self._merge_waiting_items(latest.waiting_items, extracted)

        if latest.waiting_items:
            latest.status = "waiting"
        elif latest.status == "cancelling":
            latest.status = "idle"
        elif failed:
            latest.status = "failed"
        else:
            latest.status = "idle"

        await self._session_repository.upsert(latest)

    @staticmethod
    def _merge_waiting_items(
        existing_items: list[WaitingItem],
        extracted_items: list[WaitingItem],
    ) -> list[WaitingItem]:
        preserved_statuses = {
            item.waiting_id: item.status
            for item in existing_items
            if item.status in {"resolved", "rejected"}
        }
        for item in extracted_items:
            preserved = preserved_statuses.get(item.waiting_id)
            if preserved is not None:
                item.status = preserved
        return extracted_items

    @staticmethod
    def _extract_waiting_items(runtime_session, source_runtime_id: str) -> list[WaitingItem]:
        waiting_by_id: dict[str, WaitingItem] = {}
        for message in runtime_session.state.context:
            if not isinstance(message, AssistantMsg):
                continue
            for tool_call in message.get_content_blocks("tool_call"):
                if tool_call.state == "asking":
                    waiting_by_id[tool_call.id] = WaitingItem(
                        waiting_id=tool_call.id,
                        source_type="leader",
                        source_runtime_id=source_runtime_id,
                        waiting_kind="confirm",
                        title=f"Confirm tool call: {tool_call.name}",
                        message=f"Tool {tool_call.name} requires confirmation.",
                        payload={"tool_name": tool_call.name, "tool_input": tool_call.input},
                    )
                elif tool_call.state == "submitted":
                    waiting_by_id[tool_call.id] = WaitingItem(
                        waiting_id=tool_call.id,
                        source_type="leader",
                        source_runtime_id=source_runtime_id,
                        waiting_kind="external_result",
                        title=f"Await external result: {tool_call.name}",
                        message=f"Tool {tool_call.name} is waiting for external execution result.",
                        payload={"tool_name": tool_call.name, "tool_input": tool_call.input},
                    )
        return list(waiting_by_id.values())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_runtime_service.py -v`
Expected: PASS for the new immediate-return and waiting merge tests.

- [ ] **Step 5: Commit**

```bash
git add tests/test_runtime_service.py app/services/runtime_service.py
git commit -m "feat(backend): harden runtime service mainline"
```

## Task 2: Prove Cancel Interrupts Long Runs And API Remains Asynchronous

**Files:**
- Modify: `backend/app/services/runtime_service.py`
- Modify: `backend/app/api/sessions.py`
- Modify: `backend/tests/test_session_api.py`
- Test: `backend/tests/test_session_api.py`

- [ ] **Step 1: Write the failing cancel and async API tests**

```python
import asyncio
import threading
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.storage.session_repository import SessionRepository
from app.main import create_app


def test_send_message_returns_202_before_slow_runtime_finishes() -> None:
    finished = threading.Event()

    class SlowChatRuntime:
        async def run_user_message(self, **kwargs) -> None:
            await asyncio.sleep(0.3)
            finished.set()

        async def publish_cancel(self, session_id: str) -> None:
            return None

    app = create_app()
    client = TestClient(app)
    workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
    team = client.post(
        "/api/v1/teams",
        json={"name": "Backend Team", "leader_agent_id": "leader-agent", "member_agent_ids": []},
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={"name": "Async Runtime", "workspace_id": workspace["workspace_id"], "team_id": team["team_id"]},
    ).json()

    with patch("app.api.sessions.AgentScopeChatRuntime", return_value=SlowChatRuntime()):
        started = time.perf_counter()
        response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "hello runtime"},
        )
        elapsed = time.perf_counter() - started

    assert response.status_code == 202
    assert elapsed < 0.15


def test_cancel_interrupts_slow_runtime_and_session_recovers_from_cancelling() -> None:
    cancelled = threading.Event()
    release = asyncio.Event()

    class SlowChatRuntime:
        async def run_user_message(self, **kwargs) -> None:
            try:
                await release.wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        async def publish_cancel(self, session_id: str) -> None:
            return None

    app = create_app()
    client = TestClient(app)
    workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
    team = client.post(
        "/api/v1/teams",
        json={"name": "Backend Team", "leader_agent_id": "leader-agent", "member_agent_ids": []},
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={"name": "Cancelable Runtime", "workspace_id": workspace["workspace_id"], "team_id": team["team_id"]},
    ).json()

    with patch("app.api.sessions.AgentScopeChatRuntime", return_value=SlowChatRuntime()):
        client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "long run"},
        )
        cancel_response = client.post(f"/api/v1/sessions/{created['session_id']}/cancel")

    assert cancel_response.status_code == 202

    repository = SessionRepository(get_redis_client())
    deadline = time.time() + 2.0
    final_status = None
    while time.time() < deadline:
        record = asyncio.run(repository.get(created["session_id"]))
        final_status = None if record is None else record.status
        if final_status == "idle":
            break
        time.sleep(0.05)

    assert cancelled.is_set()
    assert final_status == "idle"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_session_api.py -v`
Expected: FAIL because the current API path still waits for the slow background task to finish or cannot prove cancel interruption and recovery.

- [ ] **Step 3: Write the minimal async/cancel implementation changes**

```python
# backend/app/services/runtime_service.py
async def send_message(self, session_id: str, content: str) -> None:
    session = await self._session_repository.get(session_id)
    if session is None:
        raise KeyError(session_id)
    if session.status not in {"idle", "failed"}:
        raise ValueError("Session is not ready for a new message")

    session.status = "running"
    await self._session_repository.upsert(session)

    if self._chat_runtime is None or self._chat_run_registry is None:
        return

    async def _run_and_sync() -> None:
        run_failed = False
        try:
            await self._chat_runtime.run_user_message(
                user_id="default-user",
                session_id=session.session_id,
                agent_id=session.leader_agent_id,
                content=content,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            run_failed = True
            raise
        finally:
            await self._sync_runtime_state(
                session_id=session.session_id,
                agent_id=session.leader_agent_id,
                failed=run_failed,
            )

    self._chat_run_registry.spawn(_run_and_sync(), session_id=session.session_id)


async def cancel(self, session_id: str) -> None:
    session = await self._session_repository.get(session_id)
    if session is None:
        raise KeyError(session_id)
    session.status = "cancelling"
    await self._session_repository.upsert(session)

    task = None if self._chat_run_registry is None else self._chat_run_registry.get(session_id)
    if task is not None and not task.done():
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    if self._chat_runtime is not None:
        await self._chat_runtime.publish_cancel(session_id)
```

```python
# backend/app/api/sessions.py
@session_router.post("/{session_id}/messages", status_code=202)
async def send_message(session_id: str, body: SendMessageRequest, request: Request) -> dict:
    service = _runtime_service(request)
    try:
        await service.send_message(session_id, body.content)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "accepted", "session_id": session_id}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_session_api.py -v`
Expected: PASS for the async `202` semantics and cancel interruption tests.

- [ ] **Step 5: Commit**

```bash
git add tests/test_session_api.py app/services/runtime_service.py app/api/sessions.py
git commit -m "feat(backend): prove async runtime cancel behavior"
```

## Task 3: Add High-Fidelity Session Stream Tests

**Files:**
- Modify: `backend/app/api/session_stream.py`
- Create: `backend/tests/test_session_stream.py`
- Test: `backend/tests/test_session_stream.py`

- [ ] **Step 1: Write the failing SSE tests**

```python
import json
import time

from fastapi.testclient import TestClient

from app.main import create_app


def _read_sse_events(response, limit: int = 4) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current_event = None
    current_data = None
    for line in response.iter_lines():
        if not line:
            if current_event is not None and current_data is not None:
                events.append((current_event, json.loads(current_data)))
            current_event = None
            current_data = None
            if len(events) >= limit:
                break
            continue
        text = line.decode() if isinstance(line, bytes) else line
        if text.startswith("event: "):
            current_event = text.removeprefix("event: ")
        if text.startswith("data: "):
            current_data = text.removeprefix("data: ")
    return events


def test_session_stream_emits_ready_event() -> None:
    client = TestClient(create_app())
    workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
    team = client.post(
        "/api/v1/teams",
        json={"name": "Backend Team", "leader_agent_id": "leader-agent", "member_agent_ids": []},
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={"name": "Stream Ready", "workspace_id": workspace["workspace_id"], "team_id": team["team_id"]},
    ).json()

    with client.stream("GET", f"/api/v1/sessions/{created['session_id']}/stream") as response:
        events = _read_sse_events(response, limit=1)

    assert response.status_code == 200
    assert events[0][0] == "session.ready"
    assert events[0][1]["session_id"] == created["session_id"]


def test_session_stream_replays_or_receives_live_event_after_send_message() -> None:
    client = TestClient(create_app())
    workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
    team = client.post(
        "/api/v1/teams",
        json={"name": "Backend Team", "leader_agent_id": "leader-agent", "member_agent_ids": []},
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={"name": "Stream Live", "workspace_id": workspace["workspace_id"], "team_id": team["team_id"]},
    ).json()

    with client.stream("GET", f"/api/v1/sessions/{created['session_id']}/stream") as response:
        client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "hello stream"},
        )
        deadline = time.time() + 5.0
        events: list[tuple[str, dict]] = []
        while time.time() < deadline and len(events) < 2:
            events = _read_sse_events(response, limit=2)
            if len(events) >= 2:
                break

    assert events[0][0] == "session.ready"
    assert any(event_name == "session.event" for event_name, _payload in events[1:])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_session_stream.py -v`
Expected: FAIL if the current stream path cannot reliably expose ready/live events under test timing.

- [ ] **Step 3: Write the minimal stream stability changes**

```python
# backend/app/api/session_stream.py
from __future__ import annotations

import asyncio
from contextlib import suppress

from agentscope.app.message_bus import RedisMessageBus
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.stream.sse import encode_sse

session_stream_router = APIRouter(prefix="/sessions", tags=["session-stream"])

_HEARTBEAT_INTERVAL_SECS = 30


@session_stream_router.get("/{session_id}/stream")
async def stream_session(session_id: str) -> StreamingResponse:
    async def event_generator():
        yield encode_sse("session.ready", {"session_id": session_id, "status": "connected"})

        redis = get_redis_client()
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with message_bus:
            for _entry_id, event in await message_bus.session_read_events(session_id):
                yield encode_sse("session.event", event)

            queue: asyncio.Queue[dict | None] = asyncio.Queue()

            async def feeder() -> None:
                try:
                    async for event in message_bus.session_subscribe_events(session_id):
                        await queue.put(event)
                except asyncio.CancelledError:
                    raise
                finally:
                    await queue.put(None)

            feeder_task = asyncio.create_task(feeder(), name=f"session-stream:{session_id}")

            try:
                while True:
                    try:
                        item = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL_SECS)
                    except asyncio.TimeoutError:
                        yield ":\n\n"
                        continue
                    if item is None:
                        break
                    yield encode_sse("session.event", item)
            finally:
                feeder_task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await asyncio.wait_for(feeder_task, timeout=0.2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_session_stream.py -v`
Expected: PASS for ready and live-event SSE behavior.

- [ ] **Step 5: Commit**

```bash
git add tests/test_session_stream.py app/api/session_stream.py
git commit -m "test(backend): cover session stream live events"
```

## Task 4: Run Focused Validation And Final Sanity Checks

**Files:**
- Modify: `backend/tests/test_runtime_service.py`
- Modify: `backend/tests/test_session_api.py`
- Create: `backend/tests/test_session_stream.py`
- Modify: `backend/app/services/runtime_service.py`
- Modify: `backend/app/api/sessions.py`
- Modify: `backend/app/api/session_stream.py`

- [ ] **Step 1: Run the focused runtime/session/stream test suite**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_runtime_service.py tests/test_session_api.py tests/test_session_stream.py -v`
Expected: PASS for all newly added async mainline tests.

- [ ] **Step 2: Run the broader backend smoke tests that cover touched paths**

Run: `& ".\.venv\Scripts\python.exe" -m pytest tests/test_app.py tests/test_session_query_service.py tests/test_team_api.py tests/test_workspace_api.py -v`
Expected: PASS, confirming the async mainline changes did not regress adjacent API and query behavior.

- [ ] **Step 3: Run Ruff on modified app and test files**

Run: `& ".\.venv\Scripts\python.exe" -m ruff check app tests`
Expected: PASS with no new lint violations.

- [ ] **Step 4: Commit**

```bash
git add app/services/runtime_service.py app/api/sessions.py app/api/session_stream.py tests/test_runtime_service.py tests/test_session_api.py tests/test_session_stream.py
git commit -m "feat(backend): finalize async runtime mainline"
```
