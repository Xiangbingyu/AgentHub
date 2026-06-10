from pathlib import Path

import pytest

from app.config import Settings
from app.runtime.workspace.workspace_resolver import WorkspaceResolver


def test_workspace_session_reads_and_writes_files(tmp_path: Path) -> None:
    from app.runtime.workspace.workspace_session import WorkspaceSession

    session = WorkspaceSession(str(tmp_path))

    session.write_text("notes/todo.txt", "hello workspace")

    assert session.read_text("notes/todo.txt") == "hello workspace"


def test_workspace_session_rejects_paths_outside_workspace(tmp_path: Path) -> None:
    from app.runtime.workspace.workspace_session import WorkspaceSession

    session = WorkspaceSession(str(tmp_path))

    with pytest.raises(ValueError, match="escapes workspace root"):
        session.resolve_path("../secrets.txt")


def test_workspace_session_allows_absolute_paths_inside_workspace(tmp_path: Path) -> None:
    from app.runtime.workspace.workspace_session import WorkspaceSession

    session = WorkspaceSession(str(tmp_path))
    absolute_path = tmp_path / ".AgentHub" / "tests" / "example.py"

    session.write_text(str(absolute_path), "print('inside workspace')")

    assert absolute_path.read_text(encoding="utf-8") == "print('inside workspace')"


def test_workspace_session_respects_overwrite_flag(tmp_path: Path) -> None:
    from app.runtime.workspace.workspace_session import WorkspaceSession

    session = WorkspaceSession(str(tmp_path))
    session.write_text("README.md", "v1")

    with pytest.raises(ValueError, match="already exists"):
        session.write_text("README.md", "v2", overwrite=False)


def test_workspace_session_lists_directory_entries(tmp_path: Path) -> None:
    from app.runtime.workspace.workspace_session import WorkspaceSession

    session = WorkspaceSession(str(tmp_path))
    session.write_text("app/main.py", "print('hi')")
    session.write_text("app/utils.py", "print('utils')")

    assert session.list_dir("app") == ["main.py", "utils.py"]


def test_workspace_resolver_returns_absolute_directory(tmp_path: Path) -> None:
    resolver = WorkspaceResolver(Settings(test_workspace_path=str(tmp_path)))

    resolved = resolver.resolve_root()

    assert resolved == str(tmp_path.resolve())


def test_workspace_resolver_requires_configured_path() -> None:
    resolver = WorkspaceResolver(Settings(test_workspace_path=None))

    with pytest.raises(ValueError, match="TEST_WORKSPACE_PATH is required"):
        resolver.resolve_root()


def test_workspace_resolver_prefers_runtime_snapshot_value(tmp_path: Path) -> None:
    resolver = WorkspaceResolver(Settings(test_workspace_path=str(tmp_path / "fallback")))
    runtime_snapshot = {"workspace_root": str(tmp_path)}

    resolved = resolver.resolve(runtime_snapshot)

    assert resolved == str(tmp_path)
