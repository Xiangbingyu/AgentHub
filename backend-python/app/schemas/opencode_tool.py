from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class OpenCodeToolRequest(BaseModel):
    prompt: str


def build_opencode_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "opencode_tool",
            "description": "Delegate coding work to OpenCode inside the current workspace.",
            "parameters": OpenCodeToolRequest.model_json_schema(),
        },
    }
