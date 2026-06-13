from pathlib import Path
from uuid import uuid4

from agent_service.app.models.source_workspace import SourceWorkspaceModel
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository


def test_source_workspace_repository_creates_and_loads_record(tmp_path: Path) -> None:
    repository = SourceWorkspaceRepository()
    workspace = SourceWorkspaceModel(
        source_workspace_id=uuid4(),
        name="demo",
        root_path=str(tmp_path),
        status="ready",
    )

    repository.create(workspace)
    loaded = repository.get_by_id(workspace.source_workspace_id)

    assert loaded is not None
    assert loaded.name == "demo"
    assert loaded.status == "ready"
