from pathlib import Path

import pytest

from agent_service.app.schemas.source_workspace import SourceWorkspaceCreateRequest
from agent_service.app.services.source_workspace_service import SourceWorkspaceService


def test_create_source_workspace_persists_ready_record(tmp_path: Path) -> None:
    service = SourceWorkspaceService()
    response = service.create(SourceWorkspaceCreateRequest(name="demo", root_path=str(tmp_path)))

    assert response.name == "demo"
    assert response.status == "ready"


def test_create_source_workspace_rejects_missing_path(tmp_path: Path) -> None:
    service = SourceWorkspaceService()
    with pytest.raises(ValueError):
        service.create(
            SourceWorkspaceCreateRequest(name="ghost", root_path=str(tmp_path / "nope"))
        )


def test_create_source_workspace_rejects_file_path(tmp_path: Path) -> None:
    file_path = tmp_path / "a.txt"
    file_path.write_text("x", encoding="utf-8")
    service = SourceWorkspaceService()
    with pytest.raises(ValueError):
        service.create(SourceWorkspaceCreateRequest(name="afile", root_path=str(file_path)))

