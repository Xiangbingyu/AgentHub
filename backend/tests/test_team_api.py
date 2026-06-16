from fastapi.testclient import TestClient

from app.main import create_app


def test_list_teams_contains_default_team() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/teams")

    assert response.status_code == 200
    payload = response.json()
    assert any(team["is_default"] for team in payload["teams"])


def test_create_team_persists_leader_and_members() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["leader_agent_id"] == "leader-agent"
    assert payload["member_agent_ids"] == ["worker-a", "worker-b"]


def test_create_team_also_bootstraps_leader_agent_template() -> None:
    import asyncio

    from app.infrastructure.redis.client import get_redis_client
    from app.infrastructure.storage.team_repository import TeamRepository

    client = TestClient(create_app())

    response = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-bootstrap-agent",
            "member_agent_ids": [],
        },
    )

    assert response.status_code == 201

    repository = TeamRepository(get_redis_client())
    template = asyncio.run(repository.get_agent_template("leader-bootstrap-agent"))

    assert template is not None
    assert template.agent_id == "leader-bootstrap-agent"


def test_create_team_also_bootstraps_member_agent_templates() -> None:
    import asyncio

    from app.infrastructure.redis.client import get_redis_client
    from app.infrastructure.storage.team_repository import TeamRepository

    client = TestClient(create_app())

    response = client.post(
        "/api/v1/teams",
        json={
            "name": "Backend Team",
            "leader_agent_id": "leader-bootstrap-agent",
            "member_agent_ids": ["worker-a", "worker-b"],
        },
    )

    assert response.status_code == 201

    detail = client.get("/api/v1/teams").json()
    assert any(team["leader_agent_id"] == "leader-bootstrap-agent" for team in detail["teams"])

    async def load_templates():
        repository = TeamRepository(get_redis_client())
        return (
            await repository.get_agent_template("worker-a"),
            await repository.get_agent_template("worker-b"),
        )

    worker_a, worker_b = asyncio.run(load_templates())
    assert worker_a is not None
    assert worker_a.role == "worker"
    assert worker_b is not None
    assert worker_b.role == "worker"
