from pathlib import Path

from fastapi.testclient import TestClient

from agent_service.app.config import get_settings
from agent_service.app.main import create_app


def test_create_session_endpoint_returns_active_session(tmp_path: Path) -> None:
    client = TestClient(create_app())
    src = tmp_path / "demo"
    src.mkdir()

    source_workspace = client.post(
        "/source-workspaces",
        json={"name": "demo", "root_path": str(src)},
    ).json()
    session_workspace = client.post(
        "/session-workspaces",
        json={
            "source_workspace_id": source_workspace["source_workspace_id"],
            "name": "branch-a",
            "root_path": str(tmp_path / "demo-branch-a"),
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


def test_create_session_from_source_endpoint(tmp_path: Path, monkeypatch) -> None:
    client = TestClient(create_app())
    monkeypatch.setattr(
        get_settings(), "session_workspace_root", str(tmp_path / "session-workspaces")
    )
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.py").write_text("print('hi')\n", encoding="utf-8")

    source_workspace = client.post(
        "/source-workspaces",
        json={"name": "demo", "root_path": str(src)},
    ).json()

    response = client.post(
        "/sessions/from-source",
        json={
            "source_workspace_id": source_workspace["source_workspace_id"],
            "title": "from source",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["session_workspace_id"]


def test_create_session_from_source_missing_source_returns_400() -> None:
    from uuid import uuid4

    client = TestClient(create_app())

    response = client.post(
        "/sessions/from-source",
        json={"source_workspace_id": str(uuid4()), "title": "x"},
    )

    assert response.status_code == 400
