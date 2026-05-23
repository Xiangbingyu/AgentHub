from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunModel(BaseModel):
    run_id: UUID
    agent_id: UUID
    agent_kind: str
    workspace_id: UUID
    parent_run_id: UUID | None = None
    root_run_id: UUID | None = None
    status: str = "created"
    plan_path: str = "PLAN.md"
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
