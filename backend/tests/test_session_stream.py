import asyncio
import json
import queue
import threading
import time
from types import SimpleNamespace

from agentscope.app._tools import TeamSay
from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.storage import RedisStorage
from fastapi.testclient import TestClient

from app.api.session_stream import stream_session
from app.infrastructure.redis.client import get_redis_client
from app.main import create_app
from app.runtime.agentscope.team_runtime import AgentScopeTeamRuntime


def _read_sse_events(
    response,
    limit: int = 4,
    timeout_secs: float = 5.0,
) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    lines: queue.Queue[object] = queue.Queue()

    def _consume_lines() -> None:
        try:
            for line in response.iter_lines():
                lines.put(line)
        except BaseException as exc:  # pragma: no cover - test helper path
            lines.put(exc)
        finally:
            lines.put(None)

    thread = threading.Thread(target=_consume_lines, name="test-sse-reader", daemon=True)
    thread.start()

    current_event = None
    current_data = None
    deadline = time.time() + timeout_secs
    while len(events) < limit and time.time() < deadline:
        remaining = max(0.0, deadline - time.time())
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty as exc:
            raise AssertionError("Timed out waiting for SSE lines") from exc
        if isinstance(line, BaseException):
            raise line
        if line is None:
            break
        if not line:
            if current_event is not None and current_data is not None:
                events.append((current_event, json.loads(current_data)))
            current_event = None
            current_data = None
            continue
        text = line.decode() if isinstance(line, bytes) else line
        if text.startswith("event: "):
            current_event = text.removeprefix("event: ")
        if text.startswith("data: "):
            current_data = text.removeprefix("data: ")

    if len(events) < limit:
        raise AssertionError(
            f"Timed out waiting for {limit} SSE event(s); only received {len(events)}"
        )
    return events


def _iter_sse_events(response):
    current_event = None
    current_data = None
    for line in response.iter_lines():
        if not line:
            if current_event is not None and current_data is not None:
                yield current_event, json.loads(current_data)
            current_event = None
            current_data = None
            continue
        text = line.decode() if isinstance(line, bytes) else line
        if text.startswith("event: "):
            current_event = text.removeprefix("event: ")
        if text.startswith("data: "):
            current_data = text.removeprefix("data: ")


async def _read_stream_response_events(
    client: TestClient,
    session_id: str,
    limit: int,
    timeout_secs: float = 5.0,
) -> list[tuple[str, dict]]:
    request = SimpleNamespace(app=client.app)
    response = await stream_session(session_id, request)
    iterator = response.body_iterator.__aiter__()
    events: list[tuple[str, dict]] = []
    current_event = None
    current_data = None
    try:
        while len(events) < limit:
            chunk = await asyncio.wait_for(iterator.__anext__(), timeout=timeout_secs)
            text = chunk.decode() if isinstance(chunk, bytes) else chunk
            for line in text.splitlines():
                if not line:
                    if current_event is not None and current_data is not None:
                        events.append((current_event, json.loads(current_data)))
                        if len(events) >= limit:
                            return events
                    current_event = None
                    current_data = None
                    continue
                if line.startswith("event: "):
                    current_event = line.removeprefix("event: ")
                if line.startswith("data: "):
                    current_data = line.removeprefix("data: ")
        return events
    finally:
        await iterator.aclose()


def _create_session(client: TestClient, name: str) -> dict:
    workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
    team = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": [],
        },
    ).json()
    return client.post(
        "/api/v1/sessions",
        json={
            "name": name,
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()


def test_session_stream_emits_ready_event() -> None:
    client = TestClient(create_app())
    created = _create_session(client, "Stream Ready")

    events = asyncio.run(
        _read_stream_response_events(client, created["session_id"], limit=1),
    )

    assert events[0][0] == "session.ready"
    assert events[0][1]["session_id"] == created["session_id"]


def test_session_stream_bus_live_subscription_receives_published_event() -> None:
    client = TestClient(create_app())
    created = _create_session(client, "Stream Live")
    redis = get_redis_client()

    async def scenario() -> dict:
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with message_bus:
            ready = asyncio.Event()

            async def consume_one() -> dict:
                async for event in message_bus.session_subscribe_events(
                    created["session_id"],
                    on_ready=ready.set,
                ):
                    return event
                raise AssertionError("session_subscribe_events ended before yielding an event")

            consumer = asyncio.create_task(consume_one())
            await ready.wait()
            await message_bus.session_publish_event(
                created["session_id"],
                {"type": "test.live", "session_id": created["session_id"]},
            )
            return await asyncio.wait_for(consumer, timeout=3)

    event = asyncio.run(scenario())

    assert event["type"] == "test.live"
    assert event["session_id"] == created["session_id"]


def test_session_stream_replays_existing_event_for_late_subscriber() -> None:
    client = TestClient(create_app())
    created = _create_session(client, "Stream Replay")
    client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "hello replay"},
    )

    deadline = time.time() + 8.0
    detail = None
    while time.time() < deadline:
        detail = client.get(f"/api/v1/sessions/{created['session_id']}").json()
        if detail["messages"]:
            break
        time.sleep(0.1)

    events = asyncio.run(
        _read_stream_response_events(client, created["session_id"], limit=2),
    )

    assert detail is not None
    assert detail["messages"]
    assert events[0][0] == "session.ready"
    assert any(event_name == "session.event" for event_name, _payload in events[1:])


def test_worker_session_event_enters_replay_log() -> None:
    client = TestClient(create_app())
    workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
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
            "name": "Worker Replay Log",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()
    worker_session_id = AgentScopeTeamRuntime.build_worker_session_id(
        created["session_id"],
        "worker-a",
    )
    redis = get_redis_client()

    async def scenario() -> list[tuple[str, dict]]:
        storage = RedisStorage(connection_pool=redis.connection_pool)
        message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with storage, message_bus:
            await message_bus.session_publish_event(
                worker_session_id,
                {"type": "worker.callback", "session_id": worker_session_id},
            )
            return await message_bus.session_read_events(worker_session_id)

    events = asyncio.run(scenario())

    assert events
    assert events[0][1]["type"] == "worker.callback"


def test_runtime_team_tool_chain_wakes_leader_and_persists_hint_message() -> None:
    with TestClient(create_app()) as client:
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
                "name": "Worker Callback Wakeup",
                "workspace_id": workspace["workspace_id"],
                "team_id": team["team_id"],
            },
        ).json()

        worker_session_id = AgentScopeTeamRuntime.build_worker_session_id(
            created["session_id"],
            "worker-a",
        )

        async def send_worker_callback() -> None:
            redis = get_redis_client()
            storage = RedisStorage(connection_pool=redis.connection_pool)
            message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
            async with storage, message_bus:
                tool = TeamSay(
                    storage=storage,
                    message_bus=message_bus,
                    user_id="local-user",
                    session_id=worker_session_id,
                    agent_id="worker-a",
                    role="worker",
                )
                await tool(content="worker finished task")

        asyncio.run(send_worker_callback())

        async def await_hint_payload() -> dict:
            deadline = time.time() + 5.0
            payload = None
            while time.time() < deadline:
                await client.app.state.services.runtime_bundle.drain_wakeups_once()
                response = client.get(f"/api/v1/sessions/{created['session_id']}")
                assert response.status_code == 200
                payload = response.json()
                if any(
                    message["role"] == "assistant"
                    and any(block.get("type") == "hint" for block in message["content"])
                    for message in payload["messages"]
                ):
                    return payload
                await asyncio.sleep(0.1)
            return payload

        payload = asyncio.run(await_hint_payload())

    assert payload is not None
    assert any(
        message["role"] == "assistant"
        and any(block.get("type") == "hint" for block in message["content"])
        for message in payload["messages"]
    )


def test_runtime_team_tool_chain_callback_keeps_stream_endpoint_usable() -> None:
    with TestClient(create_app()) as client:
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
                "name": "Worker Callback Stream",
                "workspace_id": workspace["workspace_id"],
                "team_id": team["team_id"],
            },
        ).json()

        worker_session_id = AgentScopeTeamRuntime.build_worker_session_id(
            created["session_id"],
            "worker-a",
        )

        async def send_worker_callback() -> None:
            redis = get_redis_client()
            storage = RedisStorage(connection_pool=redis.connection_pool)
            message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
            async with storage, message_bus:
                tool = TeamSay(
                    storage=storage,
                    message_bus=message_bus,
                    user_id="local-user",
                    session_id=worker_session_id,
                    agent_id="worker-a",
                    role="worker",
                )
                await tool(content="worker finished task")

        events = asyncio.run(
            _read_stream_response_events(client, created["session_id"], limit=1),
        )
        assert events[0][0] == "session.ready"

        asyncio.run(send_worker_callback())

        deadline = time.time() + 5.0
        payload = None
        while time.time() < deadline:
            response = client.get(f"/api/v1/sessions/{created['session_id']}")
            assert response.status_code == 200
            payload = response.json()
            if any(
                message["role"] == "assistant"
                and any(block.get("type") == "hint" for block in message["content"])
                for message in payload["messages"]
            ):
                break
            time.sleep(0.1)

    assert any(
        message["role"] == "assistant"
        and any(block.get("type") == "hint" for block in message["content"])
        for message in payload["messages"]
    )


def test_session_detail_drains_wakeups_without_cross_loop_failure() -> None:
    with TestClient(create_app()) as client:
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
                "name": "Wakeup Drain Loop Safety",
                "workspace_id": workspace["workspace_id"],
                "team_id": team["team_id"],
            },
        ).json()

        worker_session_id = AgentScopeTeamRuntime.build_worker_session_id(
            created["session_id"],
            "worker-a",
        )

        async def send_worker_callback() -> None:
            redis = get_redis_client()
            storage = RedisStorage(connection_pool=redis.connection_pool)
            message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
            async with storage, message_bus:
                tool = TeamSay(
                    storage=storage,
                    message_bus=message_bus,
                    user_id="local-user",
                    session_id=worker_session_id,
                    agent_id="worker-a",
                    role="worker",
                )
                await tool(content="worker finished task")

        asyncio.run(send_worker_callback())

        response = client.get(f"/api/v1/sessions/{created['session_id']}")

    assert response.status_code == 200


def test_runtime_bundle_drain_processes_worker_callback_into_leader_runtime_state() -> None:
    with TestClient(create_app()) as client:
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
                "name": "Drain Wakeup Into State",
                "workspace_id": workspace["workspace_id"],
                "team_id": team["team_id"],
            },
        ).json()
        worker_session_id = AgentScopeTeamRuntime.build_worker_session_id(
            created["session_id"],
            "worker-a",
        )

        async def send_worker_callback() -> None:
            redis = get_redis_client()
            storage = RedisStorage(connection_pool=redis.connection_pool)
            message_bus = RedisMessageBus(connection_pool=redis.connection_pool)
            async with storage, message_bus:
                tool = TeamSay(
                    storage=storage,
                    message_bus=message_bus,
                    user_id="local-user",
                    session_id=worker_session_id,
                    agent_id="worker-a",
                    role="worker",
                )
                await tool(content="worker finished task")

        asyncio.run(send_worker_callback())

        async def await_leader_hint():
            deadline = time.time() + 5.0
            while time.time() < deadline:
                await client.app.state.services.runtime_bundle.drain_wakeups_once()
                response = client.get(f"/api/v1/sessions/{created['session_id']}")
                if response.status_code == 200:
                    payload = response.json()
                    if any(
                        message["role"] == "assistant"
                        and any(block.get("type") == "hint" for block in message["content"])
                        for message in payload["messages"]
                    ):
                        return payload
                await asyncio.sleep(0.1)
            return payload

        payload = asyncio.run(await_leader_hint())

    assert payload is not None
    assert any(
        message["role"] == "assistant"
        and any(block.get("type") == "hint" for block in message["content"])
        for message in payload["messages"]
    )
