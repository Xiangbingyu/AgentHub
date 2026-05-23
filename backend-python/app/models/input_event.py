from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class InputEventType(str, Enum):
    user_input = "user_input"
    worker_callback = "worker_callback"


class InputEventModel(BaseModel):
    input_id: UUID
    run_id: UUID
    type: InputEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
