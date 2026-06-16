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
