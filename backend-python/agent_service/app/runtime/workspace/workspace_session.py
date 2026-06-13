from __future__ import annotations

import shutil
from pathlib import Path


class WorkspaceSession:
    def __init__(self, workspace_root: str) -> None:
        root = Path(workspace_root).expanduser().resolve()
        if not root.exists():
            raise ValueError(f"workspace path does not exist: {root}")
        if not root.is_dir():
            raise ValueError(f"workspace path is not a directory: {root}")
        self.workspace_root = root

    def resolve_path(self, relative_path: str) -> Path:
        raw = (relative_path or ".").strip()
        target = Path(raw)
        resolved = target.resolve() if target.is_absolute() else (self.workspace_root / target).resolve()
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError as exc:
            raise ValueError(f"path escapes workspace root: {relative_path}") from exc
        return resolved

    def exists(self, relative_path: str) -> bool:
        return self.resolve_path(relative_path).exists()

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        path = self.resolve_path(relative_path)
        if not path.exists() or not path.is_file():
            raise ValueError(f"file not found: {relative_path}")
        return path.read_text(encoding=encoding)

    def write_text(
        self,
        relative_path: str,
        content: str,
        *,
        encoding: str = "utf-8",
        overwrite: bool = True,
        create_parent: bool = True,
    ) -> None:
        path = self.resolve_path(relative_path)
        if path.exists() and not overwrite:
            raise ValueError(f"path already exists: {relative_path}")
        if create_parent:
            path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)

    def mkdir(self, relative_path: str, *, parents: bool = True, exist_ok: bool = True) -> None:
        self.resolve_path(relative_path).mkdir(parents=parents, exist_ok=exist_ok)

    def list_dir(self, relative_path: str = ".") -> list[str]:
        path = self.resolve_path(relative_path)
        if not path.exists() or not path.is_dir():
            raise ValueError(f"directory not found: {relative_path}")
        return sorted(item.name for item in path.iterdir())

    def delete(self, relative_path: str, *, recursive: bool = False) -> None:
        path = self.resolve_path(relative_path)
        if not path.exists():
            raise ValueError(f"path not found: {relative_path}")
        if path.is_dir():
            if any(path.iterdir()) and not recursive:
                raise ValueError(f"recursive delete required: {relative_path}")
            if recursive:
                shutil.rmtree(path)
                return
            path.rmdir()
            return
        path.unlink()
