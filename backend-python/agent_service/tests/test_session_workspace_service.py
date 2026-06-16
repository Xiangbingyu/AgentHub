from pathlib import Path
from uuid import uuid4

import pytest

from agent_service.app.config import get_settings
from agent_service.app.database.schema import initialize_schema
from agent_service.app.database.sqlite import SQLiteDatabase
from agent_service.app.models.source_workspace import SourceWorkspaceModel
from agent_service.app.repositories.source_workspace_repository import SourceWorkspaceRepository
from agent_service.app.schemas.session_workspace import SessionWorkspaceCreateRequest
from agent_service.app.services.session_workspace_service import SessionWorkspaceService


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """把 sqlite 与受管副本根目录都指向 tmp，保证派生测试隔离。"""
    settings = get_settings()
    monkeypatch.setattr(settings, "sqlite_db_path", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "session_workspace_root", str(tmp_path / "session-workspaces"))
    conn = SQLiteDatabase(settings.sqlite_db_path).connect()
    initialize_schema(conn)
    conn.close()
    return tmp_path


def _seed_source(tmp_path: Path) -> SourceWorkspaceModel:
    src_root = tmp_path / "src"
    (src_root / "pkg").mkdir(parents=True)
    (src_root / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (src_root / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    source = SourceWorkspaceModel(
        source_workspace_id=uuid4(), name="demo", root_path=str(src_root), status="ready"
    )
    SourceWorkspaceRepository().create(source)
    return source


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


def test_derive_from_source_copies_tree(isolated_env) -> None:
    tmp_path = isolated_env
    source = _seed_source(tmp_path)

    service = SessionWorkspaceService()
    response = service.derive_from_source(source.source_workspace_id)

    assert response.source_workspace_id == source.source_workspace_id
    assert response.origin_session_workspace_id is None
    assert response.status == "ready"
    dest = Path(response.root_path)
    assert (dest / "main.py").read_text(encoding="utf-8") == "print('hello')\n"
    assert (dest / "pkg" / "mod.py").read_text(encoding="utf-8") == "x = 1\n"
    # 副本落在受管根目录下，以 session_workspace_id 命名
    assert dest.name == str(response.session_workspace_id)


def test_derive_from_missing_source_raises(isolated_env) -> None:
    service = SessionWorkspaceService()
    with pytest.raises(ValueError):
        service.derive_from_source(uuid4())


def test_derive_when_root_path_absent_raises(isolated_env) -> None:
    tmp_path = isolated_env
    source = SourceWorkspaceModel(
        source_workspace_id=uuid4(),
        name="ghost",
        root_path=str(tmp_path / "does-not-exist"),
        status="ready",
    )
    SourceWorkspaceRepository().create(source)

    service = SessionWorkspaceService()
    with pytest.raises(ValueError):
        service.derive_from_source(source.source_workspace_id)
