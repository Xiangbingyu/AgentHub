from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlanModel(BaseModel):
    plan_id: UUID
    run_id: UUID
    workspace_id: UUID
    raw_document: str = ""
    file_path: str = ""
    title: str = ""
    goal: str = ""
    status: str = "pending"
    summary: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
