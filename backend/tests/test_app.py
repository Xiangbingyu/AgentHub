from fastapi.testclient import TestClient

from app.main import create_app


def test_root_returns_service_metadata() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "AgentHub Backend is running"


def test_healthz_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agentscope_status_returns_runtime_summary() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/agentscope/status")

    assert response.status_code == 200
    payload = response.json()
    assert "installed" in payload
    assert "service_extra_ready" in payload
    assert payload["provider"] == "dashscope"


def test_app_lifespan_exposes_appservices_on_state() -> None:
    with TestClient(create_app()) as client:
        services = client.app.state.services
        assert services is not None
        assert services.runtime_principal == "local-user"
        assert services.chat_run_registry is not None


def test_app_lifespan_exposes_single_redis_client_through_appservices() -> None:
    with TestClient(create_app()) as client:
        services = client.app.state.services
        redis = services.redis_client()
        assert redis is not None
        assert services.session_repository()._redis is not None
        assert services.team_repository()._redis is not None


def test_not_found_error_uses_structured_response_shape() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/sessions/missing-session")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["message"] == "Session not found"
    assert payload["error"]["details"]["resource_type"] == "session"


def test_conflict_error_uses_structured_response_shape() -> None:
    client = TestClient(create_app())
    workspace = client.post("/api/v1/workspaces", json={"name": "Project Alpha"}).json()
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
            "name": "Conflict Session",
            "workspace_id": workspace["workspace_id"],
            "team_id": team["team_id"],
        },
    ).json()
    first = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "hello"},
    )
    assert first.status_code == 202

    response = client.post(
        f"/api/v1/sessions/{created['session_id']}/messages",
        json={"content": "hello again"},
    )

    assert response.status_code == 409
    payload = response.json()
    assert payload["error"]["code"] == "conflict"
    assert payload["error"]["details"]["resource_type"] == "session"


def test_request_logging_emits_session_route_fields(caplog) -> None:
    client = TestClient(create_app())

    with caplog.at_level("INFO"):
        response = client.get("/api/v1/sessions/missing-session")

    assert response.status_code == 404
    assert any(
        "route=session.detail" in message and "resource_type=session" in message
        for message in caplog.messages
    )
