from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class AgentRunCreateRequest(BaseModel):
    agent_id: UUID
    workspace_id: UUID
    metadata: dict[str, object] = Field(default_factory=dict)


class AgentRunCreateResponse(BaseModel):
    run_id: UUID
    agent_id: UUID
    status: str
