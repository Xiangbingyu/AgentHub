from pathlib import Path
from uuid import uuid4

from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository


def test_session_workspace_repository_lists_by_source_workspace(tmp_path: Path) -> None:
    repository = SessionWorkspaceRepository()
    source_workspace_id = uuid4()
    workspace = SessionWorkspaceModel(
        session_workspace_id=uuid4(),
        source_workspace_id=source_workspace_id,
        name="branch-a",
        root_path=str(tmp_path / "branch-a"),
        status="ready",
    )

    repository.create(workspace)
    items = repository.list_by_source_workspace_id(source_workspace_id)

    assert len(items) == 1
    assert items[0].name == "branch-a"
