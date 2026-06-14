from fastapi.testclient import TestClient

from gateway_service.app.client.agent_service_client import AgentServiceClient
from gateway_service.app.main import create_app


def test_post_message_proxies_to_agent_service(monkeypatch) -> None:
    captured = {}

    def _post_message(self, run_id, body):
        captured["run_id"] = run_id
        captured["body"] = body
        return {"run_id": run_id, "status": "accepted"}

    monkeypatch.setattr(AgentServiceClient, "post_message", _post_message)

    client = TestClient(create_app())
    payload = {"input_id": "i1", "type": "user_input", "payload": {"content": "hi"}}
    response = client.post("/agent-runs/run-1/input", json=payload)

    assert response.status_code == 200
    assert response.json() == {"run_id": "run-1", "status": "accepted"}
    assert captured["run_id"] == "run-1"
    assert captured["body"] == payload


def test_post_session_message_proxies(monkeypatch) -> None:
    captured = {}

    def _post_session_message(self, session_id, body):
        captured["session_id"] = session_id
        captured["body"] = body
        return {"run_id": "r1", "status": "accepted"}

    monkeypatch.setattr(AgentServiceClient, "post_session_message", _post_session_message)

    client = TestClient(create_app())
    response = client.post("/sessions/s-1/messages", json={"content": "hi"})

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert captured["session_id"] == "s-1"
    assert captured["body"] == {"content": "hi"}


def test_create_session_proxies(monkeypatch) -> None:
    monkeypatch.setattr(
        AgentServiceClient,
        "create_session",
        lambda self, body: {"session_id": "s1", **body},
    )

    client = TestClient(create_app())
    response = client.post("/sessions", json={"session_workspace_id": "sw1", "title": "t"})

    assert response.status_code == 200
    assert response.json()["session_id"] == "s1"


def test_cors_headers_present(monkeypatch) -> None:
    client = TestClient(create_app())
    response = client.options(
        "/sessions",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
