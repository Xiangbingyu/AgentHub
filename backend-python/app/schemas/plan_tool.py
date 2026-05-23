from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlanStepStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class PlanStepPayload(BaseModel):
    step_id: str
    content: str
    status: PlanStepStatus = PlanStepStatus.pending
    priority: str = "medium"
    owner_agent_id: UUID | None = None


class PlanSnapshot(BaseModel):
    title: str
    goal: str
    summary: str = ""
    steps: list[PlanStepPayload] = Field(default_factory=list)


class PlanToolRequest(BaseModel):
    plan: PlanSnapshot


class PlanToolResponse(BaseModel):
    plan_id: UUID
    status: str
    file_path: str
    summary: str
