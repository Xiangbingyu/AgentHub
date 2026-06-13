from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InputEventType(str, Enum):
    user_input = "user_input"
    worker_callback = "worker_callback"


class AgentRunInputRequest(BaseModel):
    input_id: UUID
    type: InputEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str


class AgentRunInputResponse(BaseModel):
    run_id: UUID
    status: str
