from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from agent_service.app.database.bootstrap import bootstrap_memory_store
from agent_service.app.main import app
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.models.source_workspace import SourceWorkspaceModel
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository

client = TestClient(app)


def test_list_and_get_source_workspace() -> None:
    bootstrap_memory_store()
    source = SourceWorkspaceRepository().create(
        SourceWorkspaceModel(
            source_workspace_id=uuid4(),
            name="src",
            root_path="E:/workspace/src",
        )
    )

    listing = client.get("/source-workspaces")
    assert listing.status_code == 200
    ids = {item["source_workspace_id"] for item in listing.json()}
    assert str(source.source_workspace_id) in ids

    detail = client.get(f"/source-workspaces/{source.source_workspace_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "src"

    assert client.get(f"/source-workspaces/{uuid4()}").status_code == 404


def test_list_session_workspaces_of_source() -> None:
    bootstrap_memory_store()
    source_id = uuid4()
    sw = SessionWorkspaceRepository().create(
        SessionWorkspaceModel(
            session_workspace_id=uuid4(),
            source_workspace_id=source_id,
            name="branch-a",
            root_path="E:/workspace/branch-a",
            status="ready",
        )
    )

    response = client.get(f"/source-workspaces/{source_id}/session-workspaces")
    assert response.status_code == 200
    ids = {item["session_workspace_id"] for item in response.json()}
    assert str(sw.session_workspace_id) in ids

    detail = client.get(f"/session-workspaces/{sw.session_workspace_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "branch-a"


def test_get_source_workspace_tree(tmp_path: Path) -> None:
    bootstrap_memory_store()
    (tmp_path / "src").mkdir()
    (tmp_path / "readme.md").write_text("y")
    source = SourceWorkspaceRepository().create(
        SourceWorkspaceModel(
            source_workspace_id=uuid4(),
            name="tree-src",
            root_path=str(tmp_path),
        )
    )

    response = client.get(
        f"/source-workspaces/{source.source_workspace_id}/tree",
        params={"path": "."},
    )
    assert response.status_code == 200
    by_name = {item["name"]: item["type"] for item in response.json()}
    assert by_name["src"] == "directory"
    assert by_name["readme.md"] == "file"


def test_get_session_workspace_tree(tmp_path: Path) -> None:
    bootstrap_memory_store()
    # 模拟 session workspace 副本目录：含 .AgentHub/plans 下的 plan 文件
    plans_dir = tmp_path / ".AgentHub" / "plans"
    plans_dir.mkdir(parents=True)
    (plans_dir / "demo.execution-plan.md").write_text("# plan", encoding="utf-8")
    sw = SessionWorkspaceRepository().create(
        SessionWorkspaceModel(
            session_workspace_id=uuid4(),
            source_workspace_id=uuid4(),
            name="branch-tree",
            root_path=str(tmp_path),
            status="ready",
        )
    )

    # 根层能看到 .AgentHub
    root_resp = client.get(f"/session-workspaces/{sw.session_workspace_id}/tree", params={"path": "."})
    assert root_resp.status_code == 200
    assert any(item["name"] == ".AgentHub" for item in root_resp.json())

    # 逐层进到 plans，能看到新写的 plan 文件
    plans_resp = client.get(
        f"/session-workspaces/{sw.session_workspace_id}/tree",
        params={"path": ".AgentHub/plans"},
    )
    assert plans_resp.status_code == 200
    names = {item["name"] for item in plans_resp.json()}
    assert "demo.execution-plan.md" in names

    # 未知 session workspace → 404
    assert client.get(f"/session-workspaces/{uuid4()}/tree").status_code == 404
