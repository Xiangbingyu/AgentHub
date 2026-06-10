from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class CodeToolRequest(BaseModel):
    action: Literal["read_file", "write_file", "list_files", "make_dir", "delete_path"]
    path: str = "."
    content: str = ""
    overwrite: bool = True
    recursive: bool = False


def build_code_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "code_tool",
            "description": "Read and write files inside the current workspace.",
            "parameters": CodeToolRequest.model_json_schema(),
        },
    }
