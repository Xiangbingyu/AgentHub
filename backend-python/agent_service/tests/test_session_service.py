from uuid import uuid4

from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.schemas.session import SessionCreateRequest
from agent_service.app.services.session_service import SessionService


def test_create_session_attaches_session_workspace() -> None:
    session_workspace = SessionWorkspaceModel(
        session_workspace_id=uuid4(),
        source_workspace_id=uuid4(),
        name="branch-a",
        root_path="E:/workspace/branch-a",
        status="ready",
    )
    SessionWorkspaceRepository().create(session_workspace)

    service = SessionService()
    response = service.create(
        SessionCreateRequest(
            session_workspace_id=session_workspace.session_workspace_id,
            title="demo session",
        )
    )

    assert response.status == "active"
    updated = SessionWorkspaceRepository().get_by_id(session_workspace.session_workspace_id)
    assert updated is not None
    assert updated.status == "attached"

    events = DomainEventRepository().list_by_session_id(response.session_id)
    assert len(events) == 1
    assert events[0].event_type == "session.message.appended"
