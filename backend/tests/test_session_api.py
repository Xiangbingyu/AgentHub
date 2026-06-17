import asyncio
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agentscope.app.storage import RedisStorage
from agentscope.event import ReplyEndEvent, ReplyStartEvent, TextBlockDeltaEvent, TextBlockStartEvent
from agentscope.message import AssistantMsg, ToolCallBlock
from fastapi.testclient import TestClient

from app.api.session_stream import stream_session
from app.domain.sessions.models import WaitingItem
from app.infrastructure.redis.client import get_redis_client
from app.infrastructure.storage.session_repository import SessionRepository
from app.main import create_app
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime
from app.runtime.agentscope.team_runtime import AgentScopeTeamRuntime


def _wait_for_session_messages(
    client: TestClient,
    session_id: str,
    *,
    timeout_secs: float = 5.0,
) -> dict:
    deadline = time.time() + timeout_secs
    last_payload: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/sessions/{session_id}")
        if response.status_code == 200:
            payload = response.json()
            last_payload = payload
            if payload["messages"]:
                return payload
        time.sleep(0.1)
    return last_payload or {"messages": []}


def _wait_for_session_condition(
    client: TestClient,
    session_id: str,
    predicate,
    *,
    timeout_secs: float = 8.0,
) -> dict:
    deadline = time.time() + timeout_secs
    last_payload: dict | None = None
    while time.time() < deadline:
        response = client.get(f"/api/v1/sessions/{session_id}")
        if response.status_code == 200:
            payload = response.json()
            last_payload = payload
            if predicate(payload):
                return payload
        time.sleep(0.1)
    return last_payload or {"messages": [], "session": {"status": "unknown"}}


def test_create_session_requires_name_workspace_and_team() -> None:
    client = TestClient(create_app())

    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()

    response = client.post(
        "/api/v1/sessions",
        json={
            "name": "Implement backend runtime",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Implement backend runtime"
    assert payload["workspace_id"] == workspace["workspace_id"]
    assert payload["team_id"] == team["team_id"]
    assert payload["status"] == "idle"


def test_get_session_detail_returns_runtime_sidebar_snapshot() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Implement backend runtime",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    response = client.get(f"/api/v1/sessions/{created['session_id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["session_id"] == created["session_id"]
    assert payload["runtime"]["waiting_items"] == []
    assert payload["workspace_status"]["workspace_id"] == workspace["workspace_id"]


def test_create_session_also_initializes_agentscope_runtime_record() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()

    response = client.post(
        "/api/v1/sessions",
        json={
            "name": "Implement backend runtime",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["leader_agent_id"] == "leader-agent"

    runtime = AgentScopeSessionStateRuntime(redis=get_redis_client())
    runtime_session = asyncio.run(
        runtime.get_runtime_session(
            "local-user",
            payload["session_id"],
            payload["leader_agent_id"],
        )
    )

    assert runtime_session is not None
    assert runtime_session.config.workspace_id == workspace["workspace_id"]


def test_create_session_also_initializes_worker_runtime_records() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()

    response = client.post(
        "/api/v1/sessions",
        json={
            "name": "Implement backend runtime",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    )

    assert response.status_code == 201
    payload = response.json()

    async def load_worker_runtime_sessions():
        runtime = AgentScopeSessionStateRuntime(redis=get_redis_client())
        return (
            await runtime.get_runtime_session(
                "local-user",
                payload["session_id"],
                "worker-a",
            ),
            await runtime.get_runtime_session(
                "local-user",
                payload["session_id"],
                "worker-b",
            ),
        )

    worker_a, worker_b = asyncio.run(load_worker_runtime_sessions())

    assert worker_a is not None
    assert worker_b is not None


def test_create_session_also_initializes_agentscope_runtime_team_record() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()

    response = client.post(
        "/api/v1/sessions",
        json={
            "name": "Implement backend runtime",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    )

    assert response.status_code == 201

    async def load_runtime_team():
        storage = RedisStorage(connection_pool=get_redis_client().connection_pool)
        async with storage:
            return await storage.get_team("local-user", team["team_id"])

    runtime_team = asyncio.run(load_runtime_team())
    assert runtime_team is not None
    assert runtime_team.id == team["team_id"]
    assert runtime_team.session_id == response.json()["session_id"]
    assert runtime_team.data.member_ids == ["worker-a", "worker-b"]


def test_send_message_persists_user_message_into_agentscope_history() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Runtime Send Message",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "hello runtime"},
    )

    assert response.status_code == 202

    _wait_for_session_messages(client, created["session_id"])

    runtime = AgentScopeSessionStateRuntime(redis=get_redis_client())
    messages = asyncio.run(
        runtime.list_runtime_messages(
            user_id="local-user",
            session_id=created["session_id"],
        )
    )

    assert any(message.get_text_content() == "hello runtime" for message in messages)


def test_session_detail_includes_assistant_reply_after_runtime_run() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Runtime Assistant Reply",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    send_response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "say hi"},
    )
    assert send_response.status_code == 202

    payload = _wait_for_session_condition(
        client,
        created["session_id"],
        lambda detail: any(
            message["role"] == "assistant" for message in detail["messages"]
        )
        or detail["session"]["status"] in {"failed", "waiting", "idle"},
        timeout_secs=12.0,
    )

    roles = [message["role"] for message in payload["messages"]]
    assert "user" in roles
    assert "assistant" in roles or payload["session"]["status"] in {"failed", "waiting", "idle"}


def test_send_message_updates_summary_snapshot_from_runtime_state() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Runtime Summary Snapshot",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    send_response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "say hi and summarize"},
    )
    assert send_response.status_code == 202

    payload = _wait_for_session_messages(client, created["session_id"])

    assert (
        payload["runtime"]["current_summary"] is not None
        or payload["session"]["status"]
        in {"idle", "running", "failed", "waiting"}
    )


def test_send_message_returns_202_before_slow_runtime_finishes() -> None:
    finished = threading.Event()

    class SlowChatRuntime:
        async def run_user_message(self, **kwargs) -> None:
            await asyncio.sleep(0.3)
            finished.set()

        async def publish_cancel(self, session_id: str) -> None:
            return None

    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": [],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Async Runtime",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    with patch(
        "app.application.services.AppServices.chat_runtime",
        return_value=SlowChatRuntime(),
    ):
        started = time.perf_counter()
        response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "hello runtime"},
        )
        elapsed = time.perf_counter() - started

    assert response.status_code == 202
    assert elapsed < 0.15
    assert not finished.is_set()


def test_send_message_does_not_fail_when_agentscope_background_manager_requires_message_bus() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": [],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Background Manager Compatibility",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "hello runtime"},
    )
    assert response.status_code == 202

    deadline = time.time() + 3.0
    payload = None
    while time.time() < deadline:
        payload = client.get(f"/api/v1/sessions/{created['session_id']}").json()
        if payload["session"]["status"] != "running":
            break
        time.sleep(0.1)

    assert payload is not None
    assert payload["session"]["status"] != "failed"


def test_cancel_interrupts_slow_runtime_and_session_recovers_from_cancelling() -> None:
    cancelled = threading.Event()

    class SlowChatRuntime:
        async def run_user_message(self, **kwargs) -> None:
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        async def publish_cancel(self, session_id: str) -> None:
            return None

    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": [],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Cancelable Runtime",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    with patch(
        "app.application.services.AppServices.chat_runtime",
        return_value=SlowChatRuntime(),
    ):
        send_response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "long run"},
        )
        cancel_response = client.post(f"/api/v1/sessions/{created['session_id']}/cancel")

    assert send_response.status_code == 202
    assert cancel_response.status_code == 202

    payload = _wait_for_session_condition(
        client,
        created["session_id"],
        lambda detail: detail["session"]["status"] == "idle",
        timeout_secs=3.0,
    )

    assert cancelled.is_set()
    assert payload["session"]["status"] == "idle"


def test_cancel_preserves_partial_assistant_reply_in_history() -> None:
    partial_reply_written = threading.Event()
    finished = threading.Event()

    class PartialReplyChatRuntime:
        async def run_user_message(self, *, user_id: str, session_id: str, agent_id: str, content: str) -> None:
            from agentscope.app.storage import RedisStorage
            from agentscope.message import AssistantMsg, TextBlock
            from app.infrastructure.redis.client import get_redis_client

            redis = get_redis_client()
            storage = RedisStorage(connection_pool=redis.connection_pool)
            async with storage:
                await storage.upsert_message(
                    user_id,
                    session_id,
                    AssistantMsg(
                        id="partial-reply-1",
                        name="leader-agent",
                        content=[TextBlock(text="半截回复")],
                    ),
                )
            partial_reply_written.set()
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                finished.set()
                raise

        async def publish_cancel(self, session_id: str) -> None:
            return None

    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": [],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Cancelable Partial Reply",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    with patch(
        "app.application.services.AppServices.chat_runtime",
        return_value=PartialReplyChatRuntime(),
    ):
        send_response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "long run"},
        )
        assert send_response.status_code == 202
        assert partial_reply_written.wait(timeout=3)
        cancel_response = client.post(f"/api/v1/sessions/{created['session_id']}/cancel")

    assert cancel_response.status_code == 202

    payload = _wait_for_session_condition(
        client,
        created["session_id"],
        lambda detail: detail["session"]["status"] == "idle",
        timeout_secs=3.0,
    )

    assert finished.is_set()
    assert any(
        message["role"] == "assistant" and "半截回复" in "".join(
            block.get("text", "") for block in message["content"] if block.get("type") == "text"
        )
        for message in payload["messages"]
    )


def test_cancel_keeps_reply_message_when_run_is_cancelled_before_completion() -> None:
    cancelled = threading.Event()

    class CancelableChatRuntime:
        async def run_user_message(self, *, user_id: str, session_id: str, agent_id: str, content: str) -> None:
            from agentscope.app.storage import RedisStorage
            from agentscope.message import AssistantMsg, TextBlock
            from app.infrastructure.redis.client import get_redis_client

            redis = get_redis_client()
            storage = RedisStorage(connection_pool=redis.connection_pool)
            async with storage:
                await storage.upsert_message(
                    user_id,
                    session_id,
                    AssistantMsg(
                        id="cancel-reply-1",
                        name="leader-agent",
                        content=[TextBlock(text="处理中回复")],
                    ),
                )
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        async def publish_cancel(self, session_id: str) -> None:
            return None

    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": [],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Cancelable Partial Reply",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    with patch(
        "app.application.services.AppServices.chat_runtime",
        return_value=CancelableChatRuntime(),
    ):
        send_response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "long run"},
        )
        assert send_response.status_code == 202
        deadline = time.time() + 3.0
        while time.time() < deadline:
            detail = client.get(f"/api/v1/sessions/{created['session_id']}").json()
            if any(message["role"] == "assistant" for message in detail["messages"]):
                break
            time.sleep(0.1)
        cancel_response = client.post(f"/api/v1/sessions/{created['session_id']}/cancel")

    assert cancel_response.status_code == 202
    assert cancelled.is_set()

    payload = _wait_for_session_condition(
        client,
        created["session_id"],
        lambda detail: detail["session"]["status"] == "idle",
        timeout_secs=3.0,
    )

    assert any(message["role"] == "assistant" for message in payload["messages"])


def test_cancel_preserves_reply_rebuilt_from_stream_events() -> None:
    cancelled = threading.Event()

    class EventPublishingChatRuntime:
        async def persist_partial_reply(self, *, user_id: str, session_id: str) -> None:
            from agentscope.app.message_bus import RedisMessageBus
            from agentscope.app.storage import RedisStorage
            from agentscope.message import AssistantMsg
            from app.infrastructure.redis.client import get_redis_client

            redis = get_redis_client()
            storage = RedisStorage(connection_pool=redis.connection_pool)
            message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
            async with storage, message_bus:
                entries = await message_bus.session_read_events(session_id)
                reply = AssistantMsg(id="stream-reply-1", name="leader-agent", content=[])
                for _entry_id, payload in entries:
                    reply_id = payload.get("reply_id")
                    if reply_id != "stream-reply-1":
                        continue
                    event_type = payload.get("type")
                    if event_type == ReplyStartEvent.model_fields["type"].default:
                        continue
                    if event_type == TextBlockStartEvent.model_fields["type"].default:
                        reply.append_event(TextBlockStartEvent.model_validate(payload))
                    elif event_type == TextBlockDeltaEvent.model_fields["type"].default:
                        reply.append_event(TextBlockDeltaEvent.model_validate(payload))
                if reply.content:
                    await storage.upsert_message(user_id, session_id, reply)

        async def run_user_message(self, *, user_id: str, session_id: str, agent_id: str, content: str) -> None:
            from agentscope.app.message_bus import RedisMessageBus
            from app.infrastructure.redis.client import get_redis_client

            redis = get_redis_client()
            message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
            async with message_bus:
                await message_bus.session_publish_event(
                    session_id,
                    ReplyStartEvent(
                        session_id=session_id,
                        reply_id="stream-reply-1",
                        name="leader-agent",
                    ).model_dump(mode="json"),
                )
                await message_bus.session_publish_event(
                    session_id,
                    TextBlockStartEvent(
                        reply_id="stream-reply-1",
                        block_id="stream-block-1",
                    ).model_dump(mode="json"),
                )
                await message_bus.session_publish_event(
                    session_id,
                    TextBlockDeltaEvent(
                        reply_id="stream-reply-1",
                        block_id="stream-block-1",
                        delta="流式半截回复",
                    ).model_dump(mode="json"),
                )
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                cancelled.set()
                raise

        async def publish_cancel(self, session_id: str) -> None:
            return None

    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": [],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Cancelable Stream Reply",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    with patch(
        "app.application.services.AppServices.chat_runtime",
        return_value=EventPublishingChatRuntime(),
    ):
        send_response = client.post(
            f"/api/v1/sessions/{created['session_id']}/messages",
            json={"content": "long run"},
        )
        assert send_response.status_code == 202
        time.sleep(0.2)
        cancel_response = client.post(f"/api/v1/sessions/{created['session_id']}/cancel")

    assert cancel_response.status_code == 202
    assert cancelled.is_set()

    payload = _wait_for_session_condition(
        client,
        created["session_id"],
        lambda detail: detail["session"]["status"] == "idle",
        timeout_secs=3.0,
    )

    assert any(
        message["role"] == "assistant" and "流式半截回复" in "".join(
            block.get("text", "") for block in message["content"] if block.get("type") == "text"
        )
        for message in payload["messages"]
    )


def test_session_stream_returns_sse_response() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Runtime Stream",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    async def scenario() -> tuple[str, str]:
        request = SimpleNamespace(app=client.app)
        response = await stream_session(created["session_id"], request)
        iterator = response.body_iterator.__aiter__()
        try:
            first_chunk = await asyncio.wait_for(iterator.__anext__(), timeout=5)
        finally:
            await iterator.aclose()
        text = first_chunk.decode() if isinstance(first_chunk, bytes) else first_chunk
        return response.media_type, text

    media_type, first_chunk = asyncio.run(scenario())

    assert media_type == "text/event-stream"
    assert "event: session.ready" in first_chunk


def test_submit_waiting_item_resolves_item_and_triggers_continuation() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Runtime Waiting Resolve",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    async def setup_waiting_state() -> None:
        redis = get_redis_client()
        session_repo = SessionRepository(redis)
        runtime = AgentScopeSessionStateRuntime(redis=redis)
        session_record = await session_repo.get(created["session_id"])
        session_record.status = "waiting"
        session_record.waiting_items = [
            WaitingItem(
                waiting_id="tool-call-1",
                source_type="leader",
                source_runtime_id="leader-agent",
                waiting_kind="confirm",
                title="Confirm tool call",
                message="Write requires confirmation",
                payload={"tool_name": "Write"},
            )
        ]
        await session_repo.upsert(session_record)

        runtime_session = await runtime.get_runtime_session(
            "local-user",
            created["session_id"],
            created["leader_agent_id"],
        )
        runtime_session.state.context = [
            AssistantMsg(
                name="leader-agent",
                content=[
                    ToolCallBlock(
                        id="tool-call-1",
                        name="Write",
                        input='{"path":"foo.py"}',
                        state="asking",
                    )
                ],
            )
        ]
        await runtime.update_runtime_state(
            "local-user",
            created["session_id"],
            created["leader_agent_id"],
            runtime_session.state,
        )

    asyncio.run(setup_waiting_state())

    with patch(
        "app.runtime.agentscope.chat_runtime.AgentScopeChatRuntime.continue_with_confirm_event",
        new_callable=AsyncMock,
    ) as mocked_continue:
        response = client.post(
            f"/api/v1/sessions/{created['session_id']}/waiting/tool-call-1",
            json={"confirmed": True},
        )

    assert response.status_code == 200
    assert mocked_continue.await_count == 1

    payload = client.get(f"/api/v1/sessions/{created['session_id']}").json()
    assert payload["runtime"]["waiting_items"][0]["status"] == "resolved"


def test_session_detail_includes_subagent_waiting_item_source() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Worker Waiting",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    async def setup_subagent_waiting_state() -> None:
        redis = get_redis_client()
        runtime = AgentScopeSessionStateRuntime(redis=redis)
        worker_session_id = AgentScopeTeamRuntime.build_worker_session_id(
            created["session_id"],
            "worker-a",
        )
        runtime_session = await runtime.get_runtime_session(
            "local-user",
            worker_session_id,
            "worker-a",
        )
        runtime_session.state.context = [
            AssistantMsg(
                name="worker-a",
                content=[
                    ToolCallBlock(
                        id="worker-tool-call-1",
                        name="Write",
                        input='{"path":"foo.py"}',
                        state="asking",
                    )
                ],
            )
        ]
        await runtime.update_runtime_state(
            "local-user",
            worker_session_id,
            "worker-a",
            runtime_session.state,
        )

    asyncio.run(setup_subagent_waiting_state())

    detail = client.get(f"/api/v1/sessions/{created['session_id']}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["runtime"]["waiting_items"][0]["source_type"] == "subagent"
    assert payload["runtime"]["waiting_items"][0]["source_runtime_id"] == "worker-a"


def test_cancel_session_sets_cancelling_and_publishes_cancel() -> None:
    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Runtime Cancel",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    with patch(
        "app.runtime.agentscope.chat_runtime.AgentScopeChatRuntime.publish_cancel",
        new_callable=AsyncMock,
    ) as mocked_cancel:
        response = client.post(f"/api/v1/sessions/{created['session_id']}/cancel")

    assert response.status_code == 202
    assert mocked_cancel.await_count == 1

    payload = client.get(f"/api/v1/sessions/{created['session_id']}").json()
    assert payload["session"]["status"] == "cancelling"
    assert payload["runtime"]["agent_statuses"][0]["status"] == "cancelled"


def test_session_detail_reads_plan_snapshot_from_workspace_file() -> None:
    from pathlib import Path

    client = TestClient(create_app())
    workspace = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    ).json()
    created = client.post(
        "/api/v1/sessions",
        json={
            "name": "Runtime Plan Snapshot",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    plan_dir = Path(workspace["root_path"]) / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)
    plan_file = plan_dir / "current-plan.json"
    plan_file.write_text(
        (
            '{"title":"Current Plan","steps":'
            '[{"content":"Do thing","status":"in_progress"}]}'
        ),
        encoding="utf-8",
    )

    detail = client.get(f"/api/v1/sessions/{created['session_id']}")
    assert detail.status_code == 200
    payload = detail.json()

    assert payload["runtime"]["current_plan"]["title"] == "Current Plan"
