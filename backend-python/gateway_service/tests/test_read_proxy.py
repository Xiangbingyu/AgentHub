from fastapi.testclient import TestClient

from gateway_service.app.client.agent_service_client import AgentServiceClient
from gateway_service.app.main import create_app


def test_list_sessions_proxy(monkeypatch) -> None:
    monkeypatch.setattr(
        AgentServiceClient,
        "list_sessions",
        lambda self: [{"session_id": "s1", "title": "demo", "status": "active"}],
    )

    client = TestClient(create_app())
    response = client.get("/sessions")

    assert response.status_code == 200
    assert response.json()[0]["session_id"] == "s1"


def test_list_source_workspaces_proxy(monkeypatch) -> None:
    monkeypatch.setattr(
        AgentServiceClient,
        "list_source_workspaces",
        lambda self: [{"source_workspace_id": "ws1", "name": "src"}],
    )

    client = TestClient(create_app())
    response = client.get("/source-workspaces")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "src"


def test_workspace_tree_proxy(monkeypatch) -> None:
    captured = {}

    def _tree(self, wid, path="."):
        captured["wid"] = wid
        captured["path"] = path
        return [{"type": "file", "name": "a.py", "path": "a.py"}]

    monkeypatch.setattr(AgentServiceClient, "get_workspace_tree", _tree)

    client = TestClient(create_app())
    response = client.get("/source-workspaces/ws1/tree", params={"path": "src"})

    assert response.status_code == 200
    assert response.json()[0]["name"] == "a.py"
    assert captured["wid"] == "ws1"
    assert captured["path"] == "src"
