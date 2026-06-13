from fastapi.testclient import TestClient

from agent_service.app.main import create_app


def test_create_session_endpoint_returns_active_session() -> None:
    client = TestClient(create_app())

    source_workspace = client.post(
        "/source-workspaces",
        json={"name": "demo", "root_path": "E:/workspace/demo"},
    ).json()
    session_workspace = client.post(
        "/session-workspaces",
        json={
            "source_workspace_id": source_workspace["source_workspace_id"],
            "name": "branch-a",
            "root_path": "E:/workspace/demo-branch-a",
        },
    ).json()

    response = client.post(
        "/sessions",
        json={
            "session_workspace_id": session_workspace["session_workspace_id"],
            "title": "demo session",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
