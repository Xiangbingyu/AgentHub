from __future__ import annotations

from app.schemas.code_tool import CodeToolRequest

class CodeTool:
    def run(self, *, runtime, arguments: CodeToolRequest | dict, **_kwargs):
        workspace = runtime.workspace_session
        if workspace is None:
            raise ValueError("workspace_session is required")

        request = arguments if isinstance(arguments, CodeToolRequest) else CodeToolRequest.model_validate(arguments)
        if request.action == "read_file":
            return {"status": "ok", "content": workspace.read_text(request.path)}
        if request.action == "write_file":
            workspace.write_text(request.path, request.content, overwrite=request.overwrite)
            return {"status": "ok", "path": request.path}
        if request.action == "list_files":
            return {"status": "ok", "entries": workspace.list_dir(request.path)}
        if request.action == "make_dir":
            workspace.mkdir(request.path)
            return {"status": "ok", "path": request.path}
        if request.action == "delete_path":
            workspace.delete(request.path, recursive=request.recursive)
            return {"status": "ok", "path": request.path}
        raise ValueError(f"unsupported action: {request.action}")
