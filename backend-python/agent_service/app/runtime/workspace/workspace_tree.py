from __future__ import annotations

from agent_service.app.runtime.workspace.workspace_session import WorkspaceSession


def list_tree_level(workspace_root: str, relative_path: str = ".") -> list[dict[str, str]]:
    """列出 workspace 中某一层目录项，单层返回，供前端按需逐层展开。

    复用 ``WorkspaceSession`` 的越界保护：越界路径会抛 ``ValueError``。
    每项形如 ``{"type": "directory"|"file", "name": str, "path": str}``，
    其中 ``path`` 是相对 ``workspace_root`` 的 POSIX 路径。
    """
    session = WorkspaceSession(workspace_root)
    target = session.resolve_path(relative_path)
    if not target.exists() or not target.is_dir():
        raise ValueError(f"directory not found: {relative_path}")

    entries: list[dict[str, str]] = []
    for item in sorted(target.iterdir(), key=lambda p: p.name):
        rel = item.resolve().relative_to(session.workspace_root)
        entries.append(
            {
                "type": "directory" if item.is_dir() else "file",
                "name": item.name,
                "path": rel.as_posix(),
            }
        )
    return entries
