from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.main import app

client = TestClient(app)


def test_create_source_workspace_api(tmp_path: Path) -> None:
    bootstrap_memory_store()
    src = tmp_path / "src"
    src.mkdir()

    response = client.post(
        "/source-workspaces",
        json={"name": f"src-{uuid4().hex[:6]}", "root_path": str(src)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_create_source_workspace_api_rejects_missing_path(tmp_path: Path) -> None:
    bootstrap_memory_store()

    response = client.post(
        "/source-workspaces",
        json={"name": "ghost", "root_path": str(tmp_path / "nope")},
    )

    assert response.status_code == 400
