from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ClaudeCodeToolRequest(BaseModel):
    prompt: str


def build_claude_code_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "claude_code_tool",
            "description": "Delegate coding work to Claude Code inside the current workspace.",
            "parameters": ClaudeCodeToolRequest.model_json_schema(),
        },
    }
