from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SessionStatus = Literal["idle", "running", "waiting", "cancelling", "failed"]
WaitingKind = Literal["confirm", "external_result"]
WaitingStatus = Literal["pending", "resolved", "rejected", "expired"]
AgentKind = Literal["leader", "worker"]
AgentRuntimeStatus = Literal[
    "idle",
    "running",
    "waiting",
    "completed",
    "failed",
    "cancelled",
]


class WaitingItem(BaseModel):
    waiting_id: str
    source_type: Literal["leader", "subagent"]
    source_runtime_id: str
    waiting_kind: WaitingKind
    title: str
    message: str
    payload: dict
    status: WaitingStatus = "pending"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentStatus(BaseModel):
    runtime_id: str
    agent_id: str
    name: str
    role: str
    kind: AgentKind
    status: AgentRuntimeStatus
    current_task_summary: str | None = None
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ProductSessionRecord(BaseModel):
    session_id: str
    name: str
    team_id: str
    leader_agent_id: str
    workspace_id: str
    status: SessionStatus = "idle"
    current_plan_snapshot: dict | None = None
    current_summary_snapshot: str | None = None
    waiting_items: list[WaitingItem] = Field(default_factory=list)
    agent_statuses: list[AgentStatus] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
