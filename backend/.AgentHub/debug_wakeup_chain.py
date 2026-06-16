import asyncio
import time

from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.storage import RedisStorage
from agentscope.app._tools import TeamSay
from fastapi.testclient import TestClient

from app.infrastructure.redis.client import get_redis_client
from app.main import create_app
from app.runtime.agentscope.team_runtime import AgentScopeTeamRuntime
from app.runtime.agentscope.state_runtime import AgentScopeSessionStateRuntime


with TestClient(create_app()) as client:
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
            "name": "Wakeup Debug",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()

    worker_session_id = AgentScopeTeamRuntime.build_worker_session_id(created["session_id"], "worker-a")

    async def send_and_check() -> None:
        redis = get_redis_client()
        storage = RedisStorage(connection_pool=redis.connection_pool)
        bus = RedisMessageBus(connection_pool=redis.connection_pool)
        async with storage, bus:
            tool = TeamSay(
                storage=storage,
                message_bus=bus,
                user_id="local-user",
                session_id=worker_session_id,
                agent_id="worker-a",
                role="worker",
            )
            result = await tool(content="worker finished task")
            print("TEAM_SAY_RESULT", result.content)
            print("INBOX_IMMEDIATE", await bus.inbox_drain(created["session_id"], max_count=10))

    asyncio.run(send_and_check())

    deadline = time.time() + 10.0
    while time.time() < deadline:
        payload = client.get(f"/api/v1/sessions/{created['session_id']}").json()
        print("STATUS", payload["session"]["status"], "MESSAGES", len(payload["messages"]))
        if payload["messages"]:
            print(payload["messages"])
        time.sleep(0.5)

    async def final_check() -> None:
        runtime = AgentScopeSessionStateRuntime(redis=get_redis_client())
        messages = await runtime.list_runtime_messages("local-user", created["session_id"])
        print("RUNTIME_MSGS", [m.model_dump(mode="json") for m in messages])

    asyncio.run(final_check())
