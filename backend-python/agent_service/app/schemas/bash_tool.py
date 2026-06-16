from __future__ import annotations

from pydantic import BaseModel, Field


class BashToolRequest(BaseModel):
    command: str = Field(min_length=1)
    description: str = Field(min_length=1)
    timeout: int | None = Field(default=None, gt=0)
    workdir: str | None = None


def build_bash_tool_definition() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "bash_tool",
            "description": "Execute a shell command inside the current workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute."},
                    "description": {"type": "string", "description": "Short description of what the command does."},
                    "timeout": {
                        "type": "integer",
                        "description": "Optional timeout in milliseconds.",
                        "minimum": 1,
                    },
                    "workdir": {
                        "type": "string",
                        "description": "Optional working directory relative to the workspace root.",
                    },
                },
                "required": ["command", "description"],
                "additionalProperties": False,
            },
        },
    }
