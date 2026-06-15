from __future__ import annotations

from agent_service.app.runtime.workspace.workspace_session import WorkspaceSession

# 单文件预览大小上限，超过则不返回内容（避免把大文件灌进响应）
MAX_PREVIEW_BYTES = 512 * 1024


def read_file_content(workspace_root: str, relative_path: str) -> dict:
    """读取 workspace 内某个文件的文本内容，供前端预览。

    复用 ``WorkspaceSession`` 的越界保护：越界路径抛 ``ValueError``。
    返回 ``{path, size, encoding, truncated, binary, content}``：
    - 二进制文件不返回内容，``binary=True``、``content=""``。
    - 超过 ``MAX_PREVIEW_BYTES`` 的文本只返回前缀，``truncated=True``。
    """
    session = WorkspaceSession(workspace_root)
    target = session.resolve_path(relative_path)
    if not target.exists() or not target.is_file():
        raise ValueError(f"file not found: {relative_path}")

    raw = target.read_bytes()
    size = len(raw)

    # NUL 字节作为二进制启发式判断
    if b"\x00" in raw[:8192]:
        return {
            "path": relative_path,
            "size": size,
            "encoding": "binary",
            "truncated": False,
            "binary": True,
            "content": "",
        }

    truncated = size > MAX_PREVIEW_BYTES
    chunk = raw[:MAX_PREVIEW_BYTES] if truncated else raw
    try:
        content = chunk.decode("utf-8")
    except UnicodeDecodeError:
        content = chunk.decode("utf-8", errors="replace")

    return {
        "path": relative_path,
        "size": size,
        "encoding": "utf-8",
        "truncated": truncated,
        "binary": False,
        "content": content,
    }
