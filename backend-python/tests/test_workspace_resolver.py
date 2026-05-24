from pathlib import Path

import pytest

from app.config import Settings
from app.runtime.workspace_resolver import WorkspaceResolver


def test_workspace_resolver_returns_absolute_directory(tmp_path: Path) -> None:
    resolver = WorkspaceResolver(Settings(test_workspace_path=str(tmp_path)))

    resolved = resolver.resolve_root()

    assert resolved == str(tmp_path.resolve())


def test_workspace_resolver_requires_configured_path() -> None:
    resolver = WorkspaceResolver(Settings(test_workspace_path=None))

    with pytest.raises(ValueError, match="TEST_WORKSPACE_PATH is required"):
        resolver.resolve_root()
