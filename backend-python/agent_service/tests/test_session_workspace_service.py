from pathlib import Path
from uuid import uuid4

from agent_service.app.schemas.session_workspace import SessionWorkspaceCreateRequest
from agent_service.app.services.session_workspace_service import SessionWorkspaceService


def test_create_session_workspace_for_source_workspace(tmp_path: Path) -> None:
    service = SessionWorkspaceService()
    response = service.create(
        SessionWorkspaceCreateRequest(
            source_workspace_id=uuid4(),
            name="branch-a",
            root_path=str(tmp_path / "branch-a"),
        )
    )

    assert response.name == "branch-a"
    assert response.status == "ready"
