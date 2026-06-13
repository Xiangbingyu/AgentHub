from uuid import uuid4

from agent_service.app.models.session import SessionModel
from agent_service.app.repositories.session_repository import SessionRepository


def test_session_repository_creates_active_session() -> None:
    repository = SessionRepository()
    session = SessionModel(
        session_id=uuid4(),
        session_workspace_id=uuid4(),
        title="demo session",
        status="active",
    )

    repository.create(session)
    loaded = repository.get_by_id(session.session_id)

    assert loaded is not None
    assert loaded.status == "active"
