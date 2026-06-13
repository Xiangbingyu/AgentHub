from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AgentRunModel(BaseModel):
    run_id: UUID
    session_id: UUID | None = None
    agent_id: UUID
    role: str | None = None
    agent_kind: str
    workspace_id: UUID
    parent_run_id: UUID | None = None
    root_run_id: UUID | None = None
    status: str = "created"
    plan_path: str = "PLAN.md"
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    runtime_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _sync_role_and_kind(self) -> AgentRunModel:
        resolved_role = self.role or self.agent_kind
        self.role = resolved_role
        self.agent_kind = resolved_role
        return self
