from pathlib import Path
from uuid import uuid4

from agent_service.app.config import get_settings
from agent_service.app.models.session_workspace import SessionWorkspaceModel
from agent_service.app.models.source_workspace import SourceWorkspaceModel
from agent_service.app.repositories.domain_event_repository import DomainEventRepository
from agent_service.app.repositories.session_workspace_repository import SessionWorkspaceRepository
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository
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


def test_create_from_source_derives_workspace_and_session(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        get_settings(), "session_workspace_root", str(tmp_path / "session-workspaces")
    )
    src_root = tmp_path / "src"
    src_root.mkdir()
    (src_root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    source = SourceWorkspaceModel(
        source_workspace_id=uuid4(), name="demo", root_path=str(src_root), status="ready"
    )
    SourceWorkspaceRepository().create(source)

    service = SessionService()
    response = service.create_from_source(source.source_workspace_id, title="from source")

    assert response.status == "active"
    # 派生出的 session workspace 真实存在且 attached
    derived = SessionWorkspaceRepository().get_by_id(response.session_workspace_id)
    assert derived is not None
    assert derived.source_workspace_id == source.source_workspace_id
    assert derived.status == "attached"
    assert (Path(derived.root_path) / "main.py").read_text(encoding="utf-8") == "print('hi')\n"

    events = DomainEventRepository().list_by_session_id(response.session_id)
    assert any(e.event_type == "session.message.appended" for e in events)


def test_create_from_source_missing_source_raises() -> None:
    service = SessionService()
    try:
        service.create_from_source(uuid4(), title="x")
    except ValueError:
        return
    raise AssertionError("expected ValueError for missing source workspace")
