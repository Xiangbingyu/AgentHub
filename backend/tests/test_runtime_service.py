import asyncio
import threading
import time
from types import SimpleNamespace

from agentscope.message import AssistantMsg, ToolCallBlock, UserMsg

from app.domain.sessions.models import ProductSessionRecord, WaitingItem
from app.runtime.agentscope.assembler import RuntimeAssembly
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime
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


def test_runtime_assembly_uses_team_leader_as_runtime_agent() -> None:
    assembly = RuntimeAssembly(
        session_id="session-1",
        runtime_agent_id="leader-agent",
        workspace_id="workspace-1",
    )

    assert assembly.runtime_agent_id == "leader-agent"


def test_runtime_state_helper_builds_session_config() -> None:
    runtime = AgentScopeSessionStateRuntime(storage=None)

    config = runtime.build_session_config(
        workspace_id="workspace-1",
        name="Demo",
    )

    assert config.workspace_id == "workspace-1"
    assert config.name == "Demo"


def test_runtime_service_send_message_requires_idle_or_failed() -> None:
    record = ProductSessionRecord(
        session_id="session-1",
        name="Demo",
        team_id="team-1",
        leader_agent_id="leader-agent",
        workspace_id="workspace-1",
    )
    repository = StubSessionRepository(record)
    service = RuntimeService(repository)

    import asyncio

    asyncio.run(service.send_message("session-1", "hello"))
    assert repository.record.status == "running"


def test_runtime_service_extracts_confirm_waiting_item_from_runtime_session() -> None:
    message = AssistantMsg(
        name="leader",
        content=[
            ToolCallBlock(
                id="tool-call-1",
                name="Write",
                input='{"path":"foo.py"}',
                state="asking",
            )
        ],
    )
    runtime_session = SimpleNamespace(
        state=SimpleNamespace(context=[message]),
    )

    waiting_items = RuntimeService._extract_waiting_items(
        runtime_session,
        source_runtime_id="leader-agent",
    )

    assert len(waiting_items) == 1
    assert waiting_items[0].waiting_kind == "confirm"
    assert waiting_items[0].waiting_id == "tool-call-1"


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
        assert repository.record.status == "running"
        task = registry.get("session-1")
        assert task is not None
        await task
        return elapsed

    elapsed = asyncio.run(scenario())

    assert elapsed < 0.1
    assert finished.is_set()
    assert repository.record.status == "idle"


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


def test_runtime_service_merge_waiting_items_keeps_subagent_source_type() -> None:
    extracted = [
        WaitingItem(
            waiting_id="wait-worker-1",
            source_type="subagent",
            source_runtime_id="worker-a",
            waiting_kind="confirm",
            title="Confirm tool call: Write",
            message="Tool Write requires confirmation.",
            payload={"tool_name": "Write", "tool_input": '{"path":"foo.py"}'},
        )
    ]

    merged = RuntimeService._merge_waiting_items([], extracted)

    assert merged[0].source_type == "subagent"
    assert merged[0].source_runtime_id == "worker-a"


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


def test_confirm_runtime_builds_user_confirm_result_event() -> None:
    from agentscope.message import ToolCallBlock

    from app.runtime.agentscope.confirm_runtime import ConfirmRuntime

    tool_call = ToolCallBlock(
        id="tool-call-1",
        name="Write",
        input='{"path":"foo.py"}',
        state="asking",
    )

    runtime = ConfirmRuntime()
    event = runtime.build_confirm_event(
        reply_id="reply-1",
        confirmed=True,
        tool_call=tool_call,
    )

    assert event.reply_id == "reply-1"
    assert len(event.confirm_results) == 1
    assert event.confirm_results[0].tool_call.id == "tool-call-1"
