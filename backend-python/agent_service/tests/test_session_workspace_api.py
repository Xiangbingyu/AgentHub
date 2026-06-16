from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from agent_service.app.config import get_settings
from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.main import app
from agent_service.app.models.source_workspace import SourceWorkspaceModel
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository

client = TestClient(app)


def test_derive_session_workspace_api(tmp_path: Path, monkeypatch) -> None:
    bootstrap_memory_store()
    monkeypatch.setattr(
        get_settings(), "session_workspace_root", str(tmp_path / "session-workspaces")
    )

    src_root = tmp_path / "src"
    src_root.mkdir()
    (src_root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    source = SourceWorkspaceRepository().create(
        SourceWorkspaceModel(
            source_workspace_id=uuid4(), name="demo", root_path=str(src_root), status="ready"
        )
    )

    response = client.post(
        "/session-workspaces/derive",
        json={"source_workspace_id": str(source.source_workspace_id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["source_workspace_id"] == str(source.source_workspace_id)
    assert body["origin_session_workspace_id"] is None
    dest = Path(body["root_path"])
    assert (dest / "main.py").read_text(encoding="utf-8") == "print('hi')\n"


def test_derive_session_workspace_api_missing_source_returns_400() -> None:
    bootstrap_memory_store()

    response = client.post(
        "/session-workspaces/derive",
        json={"source_workspace_id": str(uuid4())},
    )

    assert response.status_code == 400
