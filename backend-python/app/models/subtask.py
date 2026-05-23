from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class SubtaskModel(BaseModel):
    subtask_id: UUID
    root_run_id: UUID
    parent_run_id: UUID
    worker_run_id: UUID | None = None
    status: str = "created"
    task_prompt: str = ""
    result_ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
