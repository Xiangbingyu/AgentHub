from __future__ import annotations

from pathlib import Path


class WorkspaceFileBrowser:
    def list_tree(self, root_path: str, relative_path: str = "") -> list[dict]:
        base = Path(root_path).resolve()
        target = (base / relative_path).resolve()
        if base not in [target, *target.parents]:
            raise ValueError("Path escapes workspace root")
        if not target.exists():
            return []
        return [
            {
                "name": child.name,
                "path": child.relative_to(base).as_posix(),
                "type": "directory" if child.is_dir() else "file",
            }
            for child in sorted(
                target.iterdir(),
                key=lambda item: (item.is_file(), item.name.lower()),
            )
        ]

    def read_file(self, root_path: str, relative_path: str) -> str:
        base = Path(root_path).resolve()
        target = (base / relative_path).resolve()
        if base not in [target, *target.parents] or not target.is_file():
            raise ValueError("Invalid workspace file path")
        return target.read_text(encoding="utf-8")
