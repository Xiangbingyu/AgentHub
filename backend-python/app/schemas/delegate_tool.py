from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DelegateToolRequest(BaseModel):
    worker_agent_id: UUID
    task_prompt: str = Field(min_length=1)
    summary: str = ""


class DelegateToolResponse(BaseModel):
    subtask_id: UUID
    worker_run_id: UUID
    status: str
    summary: str


def build_delegate_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "delegate_tool",
            "description": (
                "Delegate a task to a worker agent. "
                "Provide the target worker agent id and the full task prompt."
            ),
            "parameters": DelegateToolRequest.model_json_schema(),
        },
    }
