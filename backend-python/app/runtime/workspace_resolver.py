from __future__ import annotations

from pathlib import Path

from app.config import Settings, get_settings


class WorkspaceResolver:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def resolve_root(self) -> str:
        raw_path = self.settings.test_workspace_path
        if not raw_path:
            raise ValueError("TEST_WORKSPACE_PATH is required")

        workspace_root = Path(raw_path).expanduser().resolve()
        if not workspace_root.exists():
            raise ValueError(f"workspace path does not exist: {workspace_root}")
        if not workspace_root.is_dir():
            raise ValueError(f"workspace path is not a directory: {workspace_root}")
        return str(workspace_root)
