from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


class DomainEventModel(BaseModel):
    event_id: UUID
    session_id: UUID
    session_workspace_id: UUID
    run_id: UUID | None = None
    subtask_id: UUID | None = None
    event_type: str
    event_scope: str
    payload: dict[str, object] = Field(default_factory=dict)
    sequence_no: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
