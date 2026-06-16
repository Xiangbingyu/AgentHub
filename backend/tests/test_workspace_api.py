from fastapi.testclient import TestClient

from app.main import create_app


def test_create_workspace_returns_workspace_record() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha", "description": "Main repo"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Project Alpha"
    assert payload["backend_type"] == "local"
    assert payload["root_path"]


def test_workspace_tree_lists_directory_entries() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()

    response = client.get(f"/api/v1/workspaces/{created['workspace_id']}/tree")

    assert response.status_code == 200
    assert response.json()["entries"] == []


def test_workspace_file_invalid_path_returns_structured_bad_request() -> None:
    client = TestClient(create_app())
    created = client.post(
        "/api/v1/workspaces",
        json={"name": "Project Alpha"},
    ).json()

    response = client.get(
        f"/api/v1/workspaces/{created['workspace_id']}/files",
        params={"path": "../secret.txt"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["error"]["code"] == "bad_request"
    assert payload["error"]["details"]["resource_type"] == "workspace_file"
