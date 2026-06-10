from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class CodexToolRequest(BaseModel):
    prompt: str


def build_codex_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "codex_tool",
            "description": "Delegate coding work to Codex inside the current workspace.",
            "parameters": CodexToolRequest.model_json_schema(),
        },
    }
