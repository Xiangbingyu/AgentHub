from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from agent_service.app.models.agent_mcp_config import AgentMcpConfig
from agent_service.app.models.agent_executor_config import AgentExecutorConfig
from agent_service.app.models.agent_skill_config import AgentSkillConfig
from agent_service.app.models.agent_tool_config import AgentToolsetConfig


class AgentModel(BaseModel):
    agent_id: UUID
    agent_name: str
    role: Literal["orchestrator", "worker"] | None = None
    agent_kind: Literal["orchestrator", "worker"] | None = None
    prompt_policy: dict[str, Any] = Field(default_factory=dict)
    tool_config: AgentToolsetConfig = Field(default_factory=AgentToolsetConfig)
    skill_config: AgentSkillConfig = Field(default_factory=AgentSkillConfig)
    mcp_config: AgentMcpConfig = Field(default_factory=AgentMcpConfig)
    executor_config: AgentExecutorConfig = Field(default_factory=AgentExecutorConfig)
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def _sync_role_and_kind(self) -> AgentModel:
        resolved_role = self.role or self.agent_kind
        if resolved_role is None:
            raise ValueError("role or agent_kind is required")

        self.role = resolved_role
        self.agent_kind = resolved_role
        return self
