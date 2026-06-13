from pathlib import Path

from agent_service.app.schemas.source_workspace import SourceWorkspaceCreateRequest
from agent_service.app.services.source_workspace_service import SourceWorkspaceService


def test_create_source_workspace_persists_ready_record(tmp_path: Path) -> None:
    service = SourceWorkspaceService()
    response = service.create(SourceWorkspaceCreateRequest(name="demo", root_path=str(tmp_path)))

    assert response.name == "demo"
    assert response.status == "ready"
